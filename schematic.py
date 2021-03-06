"""
based on Eagle 7.5.0 DTD
"""

import attrdict
import svgwrite

import re
import pprint
import math


class BaseObject(object):
    name = ""
    MM = 10.0
    layer2color = {
        "91": "#4BA54B",  # Nets
        "93": "#9B4646",  # Pins
        "94": "#9B4646",  # Symbols
        "95": "#A5A5A5",  # Names
        "96": "#A5A5A5",  # Values
    }
    mirror = False
    spin = False
    angle = 0
    get_bool = {"no": False, "yes": True}
    attr = attrdict.AttrDict({})
    dwg = svgwrite.drawing.Drawing()

    def val2mm(self, value):
        value = float(value)
        ret = "{val:1.5f}".format(val=value * self.MM)
        return float(ret)

    def coord2mm(self, position):
        x, y = position
        return (self.val2mm(x), self.val2mm(y))

    def rot(self, rotate="R0"):
        mirror, spin, angle = re.findall(re.compile(r"([M]*)([S]*)R(\d+)"), rotate).pop()
        return (bool(mirror), bool(spin), int(angle))


class Polygon(BaseObject):
    """
    <!ELEMENT polygon (vertex)*>
              <!-- the vertices must define a valid polygon; if the last vertex is the same as the first one, it is ignored -->
    <!ATTLIST polygon
              width         %Dimension;    #REQUIRED
              layer         %Layer;        #REQUIRED
              spacing       %Dimension;    #IMPLIED
              pour          %PolygonPour;  "solid"
              isolate       %Dimension;    #IMPLIED
              orphans       %Bool;         "no"
              thermals      %Bool;         "yes"
              rank          %Int;          "0"
              >
              <!-- isolate: Only in <signal> or <package> context -->
              <!-- orphans: Only in <signal> context -->
              <!-- thermals:Only in <signal> context -->
              <!-- rank:    1..6 in <signal> context, 0 or 7 in <package> context -->
    """

    def __init__(self, obj):
        print(self.__class__.__name__)
        print(obj.keys())
        width = float(obj["@width"])
        layer = obj["@layer"]
        # "@spacing"
        fill = obj.get("@pour", "solid")

        self.stroke_fill = self.layer2color[layer]
        self.stroke_width = self.val2mm(width)
        if obj.get("vertex") is not None:
            vertexes = obj["vertex"]
            self.vertexes = [Vertex(vertex) for vertex in vertexes]
            self.vertexes.append(self.vertexes[0])

        for index, vertex in enumerate(self.vertexes[:-1]):
            x1, y1 = vertex.coord
            next_vertex = self.vertexes[index + 1]
            x2, y2 = next_vertex.coord
            if index == 0:
                self.polygon = self.dwg.path(d="M{} {}".format(x1, y1), fill="none", fill_opacity=0.5,
                                             stroke_width=self.stroke_width, stroke=self.stroke_fill)
            if vertex.curve == 0:
                self.polygon.push("L{} {}".format(x2, y2))
            else:
                large_arc = True if abs(vertex.curve) >= 180 else False
                angle_dir = "+" if vertex.curve > 0 else "-"
                rad = math.radians(vertex.curve / 2)
                dx, dy = (abs(x1 - x2), abs(y1 - y2))
                # print(x1-x2, dx, y1-y2, dy)
                d = math.sqrt(dx ** 2 + dy ** 2)
                s = math.sin(rad)
                r = abs((d / 2) / s)
                # print(d, s, r)

                # r = float(self.val2mm(r))
                self.polygon.push_arc(target=next_vertex.coord, rotation=0, r=r, large_arc=large_arc,
                                      angle_dir=angle_dir, absolute=True)

        self.polygon.push("Z")


class Vertex(BaseObject):
    """
    <!ELEMENT vertex EMPTY>
    <!ATTLIST vertex
              x             %Coord;        #REQUIRED
              y             %Coord;        #REQUIRED
              curve         %WireCurve;    "0"
              >
              <!-- curve: The curvature from this vertex to the next one -->
    """

    def __init__(self, obj):
        print(self.__class__.__name__)
        print(obj.keys())
        x = float(obj.get("@x"))
        y = float(obj.get("@y"))
        curve = obj.get("@curve", "0")

        self.coord = self.coord2mm((x, y))
        self.curve = int(curve)


class Wire(BaseObject):
    """
    <!ELEMENT wire EMPTY>
    <!ATTLIST wire
              x1            %Coord;        #REQUIRED
              y1            %Coord;        #REQUIRED
              x2            %Coord;        #REQUIRED
              y2            %Coord;        #REQUIRED
              width         %Dimension;    #REQUIRED
              layer         %Layer;        #REQUIRED
              extent        %Extent;       #IMPLIED
              style         %WireStyle;    "continuous"
              curve         %WireCurve;    "0"
              cap           %WireCap;      "round"
              >
              <!-- extent: Only applicable for airwires -->
              <!-- cap   : Only applicable if 'curve' is not zero -->
    """
    style2dasharray = {
        "continuous": "continuous",
        "shortdash": "shortdash",
    }
    stroke_linecap = "round"

    def __init__(self, obj):
        print(self.__class__.__name__)
        print(obj.keys())
        x1 = float(obj.get("@x1"))
        x2 = float(obj.get("@x2"))
        y1 = float(obj.get("@y1"))
        y2 = float(obj.get("@y2"))
        width = float(obj["@width"])
        layer = obj["@layer"]
        style = obj.get("@style", "continuous")
        curve = obj.get("@curve", "0")

        self.start = self.coord2mm((x1, y1))
        self.end = self.coord2mm((x2, y2))
        self.stroke_fill = self.layer2color[layer]
        self.stroke_width = self.val2mm(width)
        self.stroke_dasharray = self.style2dasharray[style]
        self.curve = int(curve)
        if self.curve == 0:
            self.wire = self.dwg.line(start=self.start, end=self.end, stroke=self.stroke_fill,
                                      stroke_width=self.stroke_width, stroke_linecap=self.stroke_linecap)
        #
        else:
            x, y = self.start
            self.wire = self.dwg.path(d="M{} {}".format(x, y), fill="none",
                                      stroke_width=self.stroke_width, stroke=self.stroke_fill)
            large_arc = True if abs(self.curve) >= 180 else False
            angle_dir = "+" if self.curve > 0 else "-"
            # (3.7,1.0), (3.8,1.1), theta=100deg
            # sqrt((3.7-3.8)^2 + (1.0-1.1)^2) /2 = r * sin(theta / 2)
            # r = sqrt(...) / 2 / sin(theta/2)
            rad = math.radians(self.curve / 2)
            dx, dy = self.coord2mm((x1 - x2, y1 - y2))
            r = abs(math.sqrt(dx ** 2 + dy ** 2) / 2 / math.sin(rad))
            # r = float(self.val2mm(r))
            # r = float("{r:1.8f}".format(r=self.val2mm(r)))

            self.wire.push_arc(target=self.end, rotation=0, r=r, large_arc=large_arc,
                               angle_dir=angle_dir, absolute=True)
            # print(self.wire.tostring())
        # return wire


class Rect(BaseObject):
    """
    <!ELEMENT rectangle EMPTY>
    <!ATTLIST rectangle
              x1            %Coord;        #REQUIRED
              y1            %Coord;        #REQUIRED
              x2            %Coord;        #REQUIRED
              y2            %Coord;        #REQUIRED
              layer         %Layer;        #REQUIRED
              rot           %Rotation;     "R0"
              >
    """

    def __init__(self, obj):
        print(self.__class__.__name__)
        print(obj.keys())
        x1 = float(obj.get("@x1"))
        x2 = float(obj.get("@x2"))
        y1 = float(obj.get("@y1"))
        y2 = float(obj.get("@y2"))
        layer = obj.get("@layer")
        rot = obj.get("@rot", "R0")

        self.insert = self.coord2mm((x1, y1))
        self.size = self.coord2mm((abs(x1 - x2), abs(y1 - y2)))
        self.stroke_fill = self.layer2color[layer]
        self.mirror, self.spin, self.angle = self.rot(rot)
        self.rect = self.dwg.rect(insert=self.insert, size=self.size, stroke=self.stroke_fill, fill_opacity=0.95,
                                  fill=self.stroke_fill, stroke_linecap="round")
        # print(rect.tostring())


class Text(BaseObject):
    """
    <!ELEMENT text (#PCDATA)>
    <!ATTLIST text
              x             %Coord;        #REQUIRED
              y             %Coord;        #REQUIRED
              size          %Dimension;    #REQUIRED
              layer         %Layer;        #REQUIRED
              font          %TextFont;     "proportional"
              ratio         %Int;          "8"
              rot           %Rotation;     "R0"
              align         %Align;        "bottom-left"
              distance      %Int;          "50"
              >
    """

    normalset = {"bottom": "alphabetic", "top": "hanging",
                 "left": "start", "right": "end",
                 "center": "middle", "middle": "middle",
                 }
    mirrorset = {"bottom": "text-before-edge", "top": "alphabetic",
                 "left": "end", "right": "start",
                 "hanging": "alphabetic", "alphabetic": "hanging",
                 "end": "start", "start": "end",
                 "center": "middle", "middle": "middle",
                 }
    get_font = {"vector": "Courier New",
                "proportional": "Arial",
                "fixed": "monospace"}

    def __init__(self, obj):
        print(self.__class__.__name__)
        print(obj.keys())
        x1 = float(obj.get("@x"))
        y1 = float(obj.get("@y"))
        size = float(obj.get("@size"))
        layer = obj.get("@layer")
        font = obj.get("@font", "proportional")
        rot = obj.get("@rot", "R0")
        align = obj.get("@align", "bottom-left")
        text = obj.get("#text", "")

        fontfamily = self.get_font[font]
        self.insert = self.coord2mm((x1, -y1))
        self.font_size = int(self.val2mm(size * 1.4))
        self.fill = self.layer2color[layer]
        self.mirror, self.spin, angle = self.rot(rot)
        self.dominant_baseline, self.text_anchor, self.angle = self.align(align, self.mirror, angle)
        self.text = self.dwg.text(text=text, insert=self.insert, fill=self.fill, font_size=self.font_size,
                                  font_family=fontfamily, text_anchor=self.text_anchor,
                                  dominant_baseline=self.dominant_baseline)

    def align(self, align, mirror, rotate):
        align = align.split("-")
        if len(align) == 2:
            vert, horiz = align
            baseline = self.normalset[vert]
            anchor = self.normalset[horiz] if not mirror else self.mirrorset[horiz]
        else:
            baseline = "middle"
            anchor = "middle"

        if mirror:
            if rotate in [90, 180]:
                baseline = self.mirrorset[baseline]
                anchor = self.mirrorset[anchor]
        else:
            if rotate in [180, 270]:
                baseline = self.mirrorset[baseline]
                anchor = self.mirrorset[anchor]
        if rotate % 180 == 90:
            rotate = -90
        else:
            rotate = 0
        return (baseline, anchor, rotate)


class Dimension(BaseObject):
    def __init__(self, obj):
        print(self.__class__.__name__)
        print(obj.keys())


class Circle(BaseObject):
    """
    <!ELEMENT circle EMPTY>
    <!ATTLIST circle
              x             %Coord;        #REQUIRED
              y             %Coord;        #REQUIRED
              radius        %Coord;        #REQUIRED
              width         %Dimension;    #REQUIRED
              layer         %Layer;        #REQUIRED
              >
    """

    def __init__(self, obj):
        print(self.__class__.__name__)
        print(obj.keys())
        x = float(obj["@x"])
        y = float(obj["@y"])
        radius = float(obj["@radius"])
        width = obj["@width"]
        layer = obj["@layer"]

        self.center = self.coord2mm((x, y))
        self.r = self.val2mm(radius)
        self.stroke_fill = self.layer2color[layer]
        self.stroke_width = self.val2mm(width)
        fill = self.stroke_fill if self.stroke_width == 0 else "none"
        self.circle = self.dwg.circle(center=self.center, stroke=self.stroke_fill,
                                      stroke_width=self.stroke_width, r=self.r, fill=fill)
        # print(circle.tostring())


class Pin(BaseObject):
    """
    <!ELEMENT pin EMPTY>
    <!ATTLIST pin
              name          %String;       #REQUIRED
              x             %Coord;        #REQUIRED
              y             %Coord;        #REQUIRED
              visible       %PinVisible;   "both"
              length        %PinLength;    "long"
              direction     %PinDirection; "io"
              function      %PinFunction;  "none"
              swaplevel     %Int;          "0"
              rot           %Rotation;     "R0"
              >
    """
    appear_pinname = {"off": False, "pin": True, "pad": False, "both": True}
    appear_padname = {"off": False, "pin": False, "pad": True, "both": True}
    get_func = {"none": (False, False), "dot": (True, False), "clk": (False, True), "dotclk": (True, True)}
    get_length = {"point": 0, "short": 2.54, "middle": 5.08, "long": 7.62}

    def __init__(self, obj):
        print(self.__class__.__name__)
        print(obj.keys())

        self.name = obj["@name"]
        x = float(obj["@x"])
        y = float(obj["@y"])
        visible = obj.get("@visible", "off")
        rot = obj.get("@rot", "R0")
        length = obj.get("@length", "long")
        func = obj.get("@function", "none")

        self.name = obj["@name"]
        self.start = self.coord2mm((x, y))
        offset = self.get_length[length]
        self.end = self.coord2mm((x + offset, y))

        self.pin_name = self.appear_pinname[visible]
        self.pin_number = self.appear_padname[visible]
        self.stroke = self.layer2color["93"]
        self.stroke_width = self.val2mm(0.1524)
        self.mirror, self.spin, self.angle = self.rot(rot)

        self.shape = self.dwg.g(id="{}-pin".format(self.name))
        self.dot, self.clk = self.get_func[func]
        self.get_pin(length)

        self.pin = self.dwg.g(id=self.name)
        self.pin.add(self.shape)
        self.pin.rotate(self.angle, self.start)

    def get_pin(self, length):
        offset = self.get_length[length]
        x, y = self.start
        if self.dot and offset > 0:
            offset = offset - (2.032)
            self.shape.add(
                self.dwg.circle(center=(x + self.val2mm(offset + 2.032 / 2.0), y), r=self.val2mm(1.0),
                                stroke_width=self.stroke_width,
                                stroke=self.stroke, fill="none"))
        if self.clk:
            ex, ey = self.end
            end = (ex + self.val2mm(2.032), ey)
            self.shape.add(self.dwg.line(start=(ex, ey + self.val2mm(1.016)), end=end, stroke_width=self.stroke_width,
                                         stroke=self.stroke))
            self.shape.add(self.dwg.line(start=(ex, ey + self.val2mm(-1.016)), end=end, stroke_width=self.stroke_width,
                                         stroke=self.stroke))

        x += self.val2mm(offset)
        self.shape.add(self.dwg.line(id=self.name, start=self.start, end=(x, y), stroke=self.stroke,
                                     stroke_width=self.val2mm(0.1524), stroke_linecap="round"))


class Attribute(Text):
    """
    <!ELEMENT attribute EMPTY>
    <!ATTLIST attribute
              name          %String;       #REQUIRED
              value         %String;       #IMPLIED
              x             %Coord;        #IMPLIED
              y             %Coord;        #IMPLIED
              size          %Dimension;    #IMPLIED
              layer         %Layer;        #IMPLIED
              font          %TextFont;     #IMPLIED
              ratio         %Int;          #IMPLIED
              rot           %Rotation;     "R0"
              display       %AttributeDisplay; "value"
              constant      %Bool;         "no"
              >
              <!-- display: Only in <element> or <instance> context -->
              <!-- constant:Only in <device> context -->
    """
    get_disp = {"off": "",
                "value": "{}",
                "name": "{}",
                "both": "{} = {}"
                }

    def __init__(self, obj):
        print(self.__class__.__name__)
        print(obj.keys())
        self.name = obj["@name"]
        obj["#text"] = self.name
        self.value = obj.get("@value")
        self.display = obj.get("@display", "value")
        super().__init__(obj)


class Instance(BaseObject):
    """
    <!ELEMENT instance (attribute)*>
    <!ATTLIST instance
              part          %String;       #REQUIRED
              gate          %String;       #REQUIRED
              x             %Coord;        #REQUIRED
              y             %Coord;        #REQUIRED
              smashed       %Bool;         "no"
              rot           %Rotation;     "R0"
              >
              <!-- rot: Only 0, 90, 180 or 270 -->
    """
    symbol = None
    attributes = []
    texts = None

    def __init__(self, obj):
        print(self.__class__.__name__)
        print(obj.keys())
        x = float(obj["@x"])
        y = float(obj["@y"])
        rot = obj.get("@rot", "R0")
        smashed = obj.get("@smashed", "no")

        self.gate = obj["@gate"]
        self.part = obj["@part"]
        self.name = self.dwg.text(self.part, insert=self.coord2mm((x, -y)))
        self.center = self.coord2mm((x, y))
        self.smashed = self.get_bool[smashed]
        self.mirror, self.spin, self.angle = self.rot(rot)

        if obj.get("attribute") is not None:
            attributes = obj["attribute"]
            if isinstance(attributes, list):
                self.attributes = [Attribute(attribute) for attribute in attributes]
            else:
                self.attributes = [Attribute(attributes)]

    def populate(self, libraries, parts):
        self.part = parts[self.part]
        library = libraries[self.part.library]
        self.deviceset = library.devicesets[self.part.deviceset]
        self.gate = self.deviceset.gates[self.gate]

        symbol = library.symbols[self.gate.symbol]
        self.pop_texts(symbol)

        self.symbol = symbol.symbol.copy()
        self.symbol["id"] = symbol.symbol.get_id()
        self.instance = self.dwg.use("#{}".format(symbol.name), insert=self.center, id=self.part.name)
        self.shape = symbol.shape

        rot = -1 if self.mirror else 1
        if self.mirror:
            mirrored_id = "{}F".format(self.symbol.get_id())
            self.symbol["id"] = mirrored_id
            self.symbol.scale(-1, 1)
            self.instance.href = "#{}".format(mirrored_id)
        if self.angle:
            self.instance.rotate(rot * self.angle, self.center)

    def pop_texts(self, symbol):
        self.texts = self.dwg.g(id="{}-text".format(self.name.text))
        if not self.deviceset.uservalue:
            self.part.generate_value()
        for attr in self.attributes:
            attr.text.rotate(attr.angle, attr.insert)
            if self.smashed:
                if attr.name == "NAME":
                    attr.text.text = self.part.name
                elif attr.name == "VALUE":
                    attr.text.text = self.part.value
                else:
                    attr.get_disp[attr.display].format(attr.name, attr.value)
                self.texts.add(attr.text)
        if not self.smashed:
            for text in symbol.texts:
                tx, ty = text.insert
                cx, cy = self.center
                newx = tx + cx
                newy = -cy + ty
                _text = text.text.copy()
                _text["x"] = newx
                _text["y"] = newy
                if _text.text == ">NAME":
                    _text.text = self.part.name
                elif _text.text == ">VALUE":
                    _text.text = self.part.value
                rot = 1 if self.mirror else -1
                _text.rotate(rot * self.angle, (cx, -cy))
                rot = -1 if text.mirror else 1
                _text.rotate(rot * text.angle, (newx, newy))

                self.texts.add(_text)


class Part(BaseObject):
    """
    <!ELEMENT part (attribute*, variant*)>
    <!ATTLIST part
              name          %String;       #REQUIRED
              library       %String;       #REQUIRED
              deviceset     %String;       #REQUIRED
              device        %String;       #REQUIRED
              technology    %String;       ""
              value         %String;       #IMPLIED
              >
    """
    attributes = []
    variants = []
    deviceset = None

    def __init__(self, obj):
        print(self.__class__.__name__)
        print(obj.keys())
        self.name = obj["@name"]
        self.library = obj["@library"]
        self.deviceset = obj["@deviceset"]
        self.device = obj["@device"]
        self.technology = obj.get("@technology", "")
        # self.attribute = obj.get("@attribute", "")
        self.value = obj.get("@value", "")

        if obj.get("@attribute") is not None:
            attributes = obj["@attribute"]
            if isinstance(attributes, list):
                self.attributes = [Attribute(attr) for attr in attributes]
            else:
                self.attributes = [Attribute(attributes)]

    def generate_value(self):
        if self.deviceset.count("*") > 0:
            sp = self.deviceset.split("*")
            value = "".join([sp[0],
                             self.technology,
                             sp[1],
                             self.device
                             ])
        else:
            value = "".join([self.deviceset,
                             self.device
                             ])
        if not self.value: self.value = value


class Library(BaseObject):
    """
    <!ELEMENT library (description?, packages?, symbols?, devicesets?)>
    <!ATTLIST library
              name          %String;       #REQUIRED
              >
              <!-- name: Only in libraries used inside boards or schematics -->
    """
    description = ""
    packages = None  # this matters with brd/lbr files but not with sch
    symbols = []
    devicesets = []

    def __init__(self, obj):
        print(self.__class__.__name__)
        print(obj.keys())
        # libraries = list(obj.libraries.library) if obj["libraries"] is not None else []
        self.name = obj["@name"]
        self.description = obj.get("description", "")

        if obj["symbols"] is not None:
            symbols = obj["symbols"]["symbol"]
            if isinstance(symbols, list):
                self.symbols = [Symbol(symbol) for symbol in symbols]
            else:
                self.symbols = [Symbol(symbols)]
            self.symbols = {symbol.name: symbol for symbol in self.symbols}

        if obj["devicesets"] is not None:
            devicesets = obj["devicesets"]["deviceset"]
            if isinstance(devicesets, list):
                devicesets = [Deviceset(deviceset) for deviceset in devicesets]
            else:
                devicesets = [Deviceset(devicesets)]
            self.devicesets = {deviceset.name: deviceset for deviceset in devicesets}


class Deviceset(BaseObject):
    """
    <!ELEMENT deviceset (description?, gates, devices)>
    <!ATTLIST deviceset
              name          %String;       #REQUIRED
              prefix        %String;       ""
              uservalue     %Bool;         "no"
              >
    """
    description = None
    gates = []
    devices = []

    def __init__(self, obj):
        print(self.__class__.__name__)
        print(obj.keys())
        # libraries = list(obj.libraries.library) if obj["libraries"] is not None else []
        self.name = obj["@name"]
        self.description = obj.get("description", "")
        self.prefix = obj.get("@prefix", "")
        uservalue = obj.get("@uservalue", "no")

        self.uservalue = self.get_bool[uservalue]
        if obj.get("gates") is not None:
            gates = obj["gates"]["gate"]
            if isinstance(gates, list):
                self.gates = {gate["@name"]: Gate(gate) for gate in gates}
                #
            else:
                self.gates = {gates["@name"]: Gate(gates)}

        if obj.get("devices") is not None:
            devices = obj["devices"]["device"]
            if isinstance(devices, list):
                self.devices = [Device(device) for device in devices]
            else:
                self.devices = [Device(devices)]
            for device in self.devices:
                if device.connects:
                    for connect in device.connects:
                        connect.gate = self.gates[connect.gate]


class Connect(BaseObject):
    """
    <!ELEMENT connect EMPTY>
    <!ATTLIST connect
              gate          %String;       #REQUIRED
              pin           %String;       #REQUIRED
              pad           %String;       #REQUIRED
              route         %ContactRoute; "all"
              >
    """

    def __init__(self, obj):
        print(self.__class__.__name__)
        print(obj.keys())
        self.gate = obj["@gate"]
        self.pin = obj["@pin"]
        self.pad = obj["@pad"]
        self.route = obj.get("@route", "all")
        self.connect = (self.pin, self.pad)


class Device(BaseObject):
    """
    <!ELEMENT device (connects?, technologies?)>
    <!ATTLIST device
              name          %String;       ""
              package       %String;       #IMPLIED
              >
    """
    connects = []
    technologies = None

    def __init__(self, obj):
        print(self.__class__.__name__)
        print(obj.keys())
        self.name = obj.get("@name", "")
        self.package = obj.get("@package")
        self.connects = obj.get("connects")
        self.technologies = obj.get("technologies")

        if obj.get("connects") is not None:
            connects = obj["connects"]["connect"]
            if isinstance(connects, list):
                self.connects = [Connect(connect) for connect in connects]
            else:
                self.connects = [Connect(connects)]


class Technology(BaseObject):
    """
    <!ELEMENT technology (attribute)*>
    <!ATTLIST technology
              name          %String;       #REQUIRED
              >
    """
    attributes = []

    def __init__(self, obj):
        print(self.__class__.__name__)
        print(obj.keys())
        self.name = obj["@name"]
        attributes = obj.get("attribute")
        self.attributes = [Attribute(attribute) for attribute in attributes]


class Gate(BaseObject):
    """
    <!ELEMENT gate EMPTY>
    <!ATTLIST gate
              name          %String;       #REQUIRED
              symbol        %String;       #REQUIRED
              x             %Coord;        #REQUIRED
              y             %Coord;        #REQUIRED
              addlevel      %GateAddLevel; "next"
              swaplevel     %Int;          "0"
              >
    """

    def __init__(self, obj):
        print(self.__class__.__name__)
        print(obj.keys())
        self.name = obj["@name"]
        self.symbol = obj["@symbol"]
        x = float(obj["@x"])
        y = float(obj["@y"])

        self.center = self.coord2mm((x, y))


class Frame(BaseObject):
    """
    <!ELEMENT frame EMPTY>
    <!ATTLIST frame
              x1            %Coord;       #REQUIRED
              y1            %Coord;       #REQUIRED
              x2            %Coord;       #REQUIRED
              y2            %Coord;       #REQUIRED
              columns       %Int;         #REQUIRED
              rows          %Int;         #REQUIRED
              layer         %Layer;       #REQUIRED
              border-left   %Bool;        "yes"
              border-top    %Bool;        "yes"
              border-right  %Bool;        "yes"
              border-bottom %Bool;        "yes"
              >
    """

    border = attrdict.AttrDict({})

    def __init__(self, obj):
        print(self.__class__.__name__)
        print(obj.keys())
        x1 = float(obj.get("@x1"))
        x2 = float(obj.get("@x2"))
        y1 = float(obj.get("@y1"))
        y2 = float(obj.get("@y2"))
        layer = obj.get("@layer")
        columns = obj.get("@columns")
        raws = obj.get("@rows")
        border_left = obj.get("@border-left", "yes")
        border_top = obj.get("@border-top", "yes")
        border_right = obj.get("@border-right", "yes")
        border_bottom = obj.get("@border-bottom", "yes")

        self.insert = self.coord2mm((x1, y1))
        self.size = self.coord2mm((x1 - x2, y1 - y2))
        self.stroke_fill = self.layer2color[layer]
        self.border.left = self.get_bool[border_left]
        self.border.top = self.get_bool[border_top]
        self.border.right = self.get_bool[border_right]
        self.border.bottom = self.get_bool[border_bottom]


class Net(BaseObject):
    """
    <!ELEMENT net (segment)*>
    <!ATTLIST net
              name          %String;       #REQUIRED
              class         %Class;        "0"
              >
    """
    segments = []

    def __init__(self, obj):
        print(self.__class__.__name__)
        print(obj.keys())
        self.name = obj["@name"]
        self.net = self.dwg.g(id=self.name)

        if obj.get("segment") is not None:
            segments = obj["segment"]
            if isinstance(segments, list):
                self.segments = [Segment(segment) for segment in segments]
            else:
                self.segments = [Segment(segments)]
            [self.net.add(segment.segment) for segment in self.segments]
            for segment in self.segments:
                for label in segment.labels:
                    label.label.text.text = self.name
                    angle = label.label.angle
                    insert = label.label.insert
                    label.label.text.rotate(angle, insert)


class Segment(BaseObject):
    """
    <!ELEMENT segment (pinref | portref | wire | junction | label)*>
    """
    wires = []
    junctions = []
    labels = []

    def __init__(self, obj):
        print(self.__class__.__name__)
        print(obj.keys())
        self.segment = self.dwg.g()

        if obj.get("wire") is not None:
            wires = obj["wire"]
            if isinstance(wires, list):
                self.wires = [Wire(wire) for wire in wires]
            else:
                self.wires = [Wire(wires)]
            [self.segment.add(wire.wire) for wire in self.wires]

        if obj.get("junction") is not None:
            junctions = obj["junction"]
            if isinstance(junctions, list):
                self.junctions = [Junction(junction) for junction in junctions]
            else:
                self.junctions = [Junction(junctions)]
            [self.segment.add(junction.junction) for junction in self.junctions]

        if obj.get("label") is not None:
            labels = obj["label"]
            if isinstance(labels, list):
                self.labels = [Label(label) for label in labels]
            else:
                self.labels = [Label(labels)]


class Label(BaseObject):
    """
    <!ELEMENT label EMPTY>
    <!ATTLIST label
              x             %Coord;        #REQUIRED
              y             %Coord;        #REQUIRED
              size          %Dimension;    #REQUIRED
              layer         %Layer;        #REQUIRED
              font          %TextFont;     "proportional"
              ratio         %Int;          "8"
              rot           %Rotation;     "R0"
              xref          %Bool;         "no"
              >
              <!-- rot:  Only 0, 90, 180 or 270 -->
              <!-- xref: Only in <net> context -->
    """

    def __init__(self, obj):
        print(self.__class__.__name__)
        print(obj.keys())
        obj["#text"] = ""
        self.label = Text(obj)


class Junction(BaseObject):
    """
    <!ELEMENT junction EMPTY>
    <!ATTLIST junction
              x             %Coord;        #REQUIRED
              y             %Coord;        #REQUIRED
              >
    """

    def __init__(self, obj):
        print(self.__class__.__name__)
        print(obj.keys())
        x = float(obj["@x"])
        y = float(obj["@y"])
        self.center = self.coord2mm((x, y))
        self.r = self.val2mm(0.5)
        self.stroke_fill = self.layer2color["91"]
        self.stroke_width = self.val2mm(0)
        fill = self.stroke_fill if self.stroke_width == 0 else "none"
        self.junction = self.dwg.circle(center=self.center, stroke=self.stroke_fill,
                                        stroke_width=self.stroke_width, r=self.r, fill=fill)


class Symbol(BaseObject):
    """
    <!ELEMENT symbol (description?, (polygon | wire | text | dimension | pin | circle | rectangle | frame)*)>
    <!ATTLIST symbol
              name          %String;       #REQUIRED
              >
    """
    description = None
    polygons = []
    wires = []
    texts = []
    dimensions = []
    pins = []
    circles = []
    rectangles = []
    frames = []

    def __init__(self, obj):
        print(self.__class__.__name__)
        print(obj.keys())
        self.name = obj["@name"]

        self.description = obj.get("description", "")
        if obj.get("polygon") is not None:
            polygons = obj.polygon
            if isinstance(polygons, list):
                self.polygons = [Polygon(polygon) for polygon in polygons]
            else:
                self.polygons = [Polygon(polygons)]
        #
        if obj.get("wire") is not None:
            wires = obj["wire"]
            if isinstance(wires, list):
                self.wires = [Wire(wire) for wire in wires]
            else:
                self.wires = [Wire(wires)]
        #
        if obj.get("dimension") is not None:
            dimensions = obj["dimension"]
            if isinstance(dimensions, list):
                self.dimensions = [Dimension(dimension) for dimension in dimensions]
            else:
                self.dimensions = [Dimension(dimensions)]
        #
        if obj.get("text") is not None:
            texts = obj["text"]
            if isinstance(texts, list):
                self.texts = [Text(text) for text in texts]
            else:
                self.texts = [Text(texts)]
        #
        if obj.get("pin") is not None:
            pins = obj["pin"]
            if isinstance(pins, list):
                self.pins = [Pin(pin) for pin in pins]
            else:
                self.pins = [Pin(pins)]
        #
        if obj.get("circle") is not None:
            circles = obj["circle"]
            if isinstance(circles, list):
                self.circles = [Circle(circle) for circle in circles]
            else:
                self.circles = [Circle(circles)]
        #
        if obj.get("rectangle") is not None:
            rectangles = obj["rectangle"]
            if isinstance(rectangles, list):
                self.rectangles = [Rect(rectangle) for rectangle in rectangles]
            else:
                self.rectangles = [Rect(rectangles)]
        #
        if obj.get("frame") is not None:
            frames = obj["frame"]
            if isinstance(frames, list):
                self.frames = [Frame(frame) for frame in frames]
            else:
                self.frames = [Frame(frames)]
        #
        self.shape = self.dwg.g(id="{}-shape".format(self.name))
        # symbol.scale(1, -1)

        origin = self.dwg.g(id="origin")
        origin.add(self.dwg.line(start=self.coord2mm((-1, 0)), end=self.coord2mm((1, 0)), stroke="maroon",
                                 stroke_linecap="round"))
        origin.add(self.dwg.line(start=self.coord2mm((0, -1)), end=self.coord2mm((0, 1)), stroke="maroon",
                                 stroke_linecap="round"))
        self.shape.add(origin)

        [self.shape.add(polygon.polygon) for polygon in self.polygons]
        [self.shape.add(wire.wire) for wire in self.wires]
        # [self.shape.add(dimension.dimension) for dimension in self.dimension]
        [self.shape.add(pin.pin) for pin in self.pins]
        [self.shape.add(circle.circle) for circle in self.circles]
        [self.shape.add(rectangle.rect) for rectangle in self.rectangles]

        self.symbol = self.dwg.g(id=self.name)
        self.symbol.add(self.dwg.use("#{}".format(self.shape.get_id())))


class Sheet(BaseObject):
    """
    <!ELEMENT sheet (description?, plain?, moduleinsts?, instances?, busses?, nets?)>
    """
    description = None
    plain = []
    moduleinsts = []
    instances = []
    busses = []
    nets = []
    shapes = None

    def __init__(self, obj):
        print(self.__class__.__name__)
        print(obj.keys())
        self.description = obj.get("description", "")
        self.sheet = self.dwg.g()
        self.shapes = self.dwg.g(transform="scale(1,-1)")
        self.sheet.add(self.shapes)

        if obj.get("plain") is not None:
            plain = Plain(obj["plain"])
            self.sheet.add(plain.shapes)
            self.sheet.add(plain.texts)
        #

        if obj.get("instances") is not None:
            instances = obj["instances"]["instance"]
            if isinstance(instances, list):
                self.instances = [Instance(instance) for instance in instances]
            else:
                self.instances = [Instance(instances)]

            for instance in self.instances:
                if instance.smashed:
                    [self.sheet.add(attr.text) for attr in instance.attributes]

        if obj.get("nets") is not None:
            nets = obj["nets"]["net"]
            if isinstance(nets, list):
                self.nets = [Net(net) for net in nets]
            else:
                self.nets = [Net(nets)]
            [self.shapes.add(net.net) for net in self.nets]
            [[[self.sheet.add(label.label.text) for label in segment.labels] for segment in net.segments] for net in
             self.nets]

    def populate(self, libraries, parts):
        for instance in self.instances:
            instance.populate(libraries, parts)
            self.shapes.add(instance.instance)
            self.sheet.add(instance.texts)
            self.shapes.add(instance.instance)


class Plain(BaseObject):
    """
    <!ELEMENT plain (polygon | wire | text | dimension | circle | rectangle | frame | hole)*>
    """
    polygons = []
    wires = []
    texts = []
    dimensions = []
    pins = []
    circles = []
    rectangles = []
    frames = []

    def __init__(self, obj):
        print(self.__class__.__name__)
        print(obj.keys())

        if obj.get("polygon") is not None:
            polygons = obj["polygon"]
            if isinstance(polygons, list):
                self.polygons = [Polygon(polygon) for polygon in polygons]
            else:
                self.polygons = [Polygon(polygons)]
        #
        if obj.get("wire") is not None:
            wires = obj["wire"]
            if isinstance(wires, list):
                self.wires = [Wire(wire) for wire in wires]
            else:
                self.wires = [Wire(wires)]
        #
        if obj.get("text") is not None:
            texts = obj["text"]
            if isinstance(texts, list):
                self.texts = [Text(text) for text in texts]
            else:
                self.texts = [Text(texts)]
        #
        if obj.get("dimension") is not None:
            dimensions = obj["dimension"]
            if isinstance(dimensions, list):
                self.dimensions = [Dimension(dimension) for dimension in dimensions]
            else:

                self.dimensions = [Dimension(dimensions)]
        #
        if obj.get("circle") is not None:
            circles = obj["circle"]
            if isinstance(circles, list):
                self.circles = [Circle(circle) for circle in circles]
            else:
                self.circles = [Circle(circles)]
        #
        if obj.get("rectangle") is not None:
            rectangles = obj["rectangle"]
            if isinstance(rectangles, list):
                self.rectangles = [Rect(rectangle) for rectangle in rectangles]
            else:
                self.rectangles = [Rect(rectangles)]
        #
        if obj.get("frame") is not None:
            frames = list(obj["frame"])
            if isinstance(frames, list):
                self.frames = [Frame(frame) for frame in frames]
            else:
                self.frames = [Frame(frames)]
        #
        shape = self.dwg.g(id="plain_objects")
        texts = self.dwg.g(id="plain_texts")

        [shape.add(polygon.polygon) for polygon in self.polygons]
        [shape.add(wire.wire) for wire in self.wires]
        # [shape.add(dimension.dimension) for dimension in self.dimension]

        for text in self.texts:
            angle = text.angle
            insert = text.insert
            text = text.text
            text.rotate(angle, insert)
            texts.add(text)
        [shape.add(pin.pin) for pin in self.pins]
        [shape.add(circle.circle) for circle in self.circles]
        [shape.add(rectangle.rect) for rectangle in self.rectangles]
        shape.scale(1, -1)

        self.shapes = shape
        self.texts = texts


class Schematic(BaseObject):
    """
    <!ELEMENT schematic (description?, libraries?, attributes?, variantdefs?, classes?, modules?, parts?, sheets?, errors?)>
    <!ATTLIST schematic
              xreflabel     %String;       #IMPLIED
              xrefpart      %String;       #IMPLIED
              >
    """
    description = []
    libraries = []
    attributes = []
    variantdef = []
    classes = []
    modules = []
    parts = []
    sheets = []
    errors = []
    symbols = []

    def __init__(self, obj):
        print(self.__class__.__name__)
        print(obj.keys())
        self.schematic = self.dwg.g()
        self.description = attrdict.AttrDict(obj.get("description", {}))

        if obj["libraries"] is not None:
            libraries = obj["libraries"]["library"]
            if isinstance(libraries, list):
                libraries = [Library(library) for library in libraries]
            else:
                libraries = [Library(libraries)]
            self.libraries = {library.name: library for library in libraries}

        if obj["attributes"] is not None:
            attributes = obj["attributes"]["attribute"]
            if isinstance(attributes, list):
                self.attributes = [Attribute(attribute) for attribute in attributes]
            else:
                self.attributes = [Attribute(attributes)]

        if obj["parts"] is not None:
            parts = obj["parts"]["part"]
            if isinstance(parts, list):
                parts = [Part(part) for part in parts]
            else:
                parts = [Part(parts)]
            self.parts = {part.name: part for part in parts}

        if obj["sheets"] is not None:
            sheets = obj["sheets"]["sheet"]
            if isinstance(sheets, list):
                self.sheets = [Sheet(sheet) for sheet in sheets]
            else:
                self.sheets = [Sheet(sheets)]
            for index, sheet in enumerate(self.sheets):
                sheet.populate(self.libraries, self.parts)

                for instance in sheet.instances:
                    self.symbols.append(instance.symbol)
                    self.symbols.append(instance.shape)
                    id = instance.symbol.get_id()
                    print(id)

                sheet = sheet.sheet
                sheet["id"] = "sheet{}".format(index)

                self.schematic.add(sheet)
