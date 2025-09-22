from schemdraw.elements.intcircuits import *
import schemdraw.elements as elm

from schemdraw import Drawing
import matplotlib.pyplot as plt
import schemdraw

class AIc(Element):
    _element_defaults = {
        'pinspacing': 0.0,
        'edgepadH': 0.5,
        'edgepadW': 0.5,
        'leadlen': 0.5,
        'lsize': 14,
        'lofst': 0.15,
        'plblofst': 0.075,
        'plblsize': 11
    }

    # 参数列表
    OFFSET_FACTOR = 1 / 14.0             # 相当于 d = min(w,h) * OFFSET_FACTOR
    RECT_H_FRAC = 0.06                # rect_h = RECT_H_FRAC * min(w,h)

    def __init__(self,
                 size: Optional[XY] = None,
                 pins: Optional[Sequence[IcPin]] = None,
                 slant: float = 0,
                 **kwargs):
        super().__init__(**kwargs)
        self.size = size if size is not None else self.params.get('size')
        self._sizeauto: Optional[tuple[float, float]] = None
        self.slant = slant
        self.pins: dict[Side, list[IcPin]] = {'L': [], 'R': [], 'T': [], 'B': []}
        self.usersides: dict[Side, IcSide] = {}
        self.sides: dict[Side, IcSide] = {}
        self._dflt_side = IcSide(
            self.params.get('pinspacing', 0),
            self.params.get('edgepadH', .25),
            self.params.get('leadlen', .5),
            self.params.get('lofst', .15),
            self.params.get('lsize', 14),
            self.params.get('plblofst', .05),
            self.params.get('plblsize', 11))

        if pins is not None:
            for pin in pins:
                side = cast(Side, pin.side[0].upper())
                self.pins[side].append(pin)

        self._icbox = IcBox(0,0,0,0)
        self._setsize()

    def __getattr__(self, name: str) -> Any:
        ''' Allow getting anchor position as attribute '''
        anchornames = ['start', 'end', 'center', 'istart', 'iend',
                       'N', 'S', 'E', 'W', 'NE', 'NW', 'SE', 'SW',
                       'NNE', 'NNW', 'ENE', 'WNW', 'SSE', 'SSW', 'ESE', 'WSW']
        anchornames += list(vars(self).get('anchors', {}).keys())
        anchornames += self.pinnames
        anchornames += [f'pin{p.pin}' for p in self.pins.get('L', [])]
        anchornames += [f'pin{p.pin}' for p in self.pins.get('R', [])]
        anchornames += [f'pin{p.pin}' for p in self.pins.get('T', [])]
        anchornames += [f'pin{p.pin}' for p in self.pins.get('B', [])]
        if (name in anchornames and not name in vars(self).get('absanchors', {})):
                # Not placed yet
                drawing_stack.push_element(self)

        if name in vars(self).get('absanchors', {}):
            return vars(self).get('absanchors')[name]  # type: ignore
        raise AttributeError(f'{name} not defined in Element')

    @property
    def pinnames(self) -> list[str]:
        ''' List of all pin names '''
        names: list[str] = []
        for _, pins in self.pins.items():
            names.extend(p.anchorname if p.anchorname else p.name for p in pins if p.name)
        return names

    def pin(self,
            side: Side = 'L',
            name: str | None = None,
            pin: str | None = None,
            pos: float | None = None,
            slot: str | None = None,
            invert: bool = False,
            invertradius: float = 0.15,
            color: str | None = None,
            rotation: float = 0,
            anchorname: str | None = None,
            lblsize: float | None = None,
            href: Optional[str] = None,
            decoration: Optional[str] = None):
        ''' Add a pin to the IC

            Args:
                name: Input/output name (inside the box)
                pin: Pin name/number (outside the box)
                side: Side of box for the pin, 'left', 'right', 'top', 'bottom'
                pos: Pin position along the side, fraction from 0-1
                slot: Slot definition of pin location, given in 'X/Y' format.
                    '2/4' is the second pin on a side with 4 pins.
                invert:Add an invert bubble to the pin
                invertradius: Radius of invert bubble
                color: Color for the pin and label
                rotation: Rotation for label text
                anchorname: Named anchor for the pin
                lblsize: Font size for label
                href: Hyperline target (jump to)
                decoration: "underline" or "overline"
        '''
        side = cast(Side, side[0].upper())
        self.pins[side].append(IcPin(name, pin, side, pos, slot, invert,
                                    invertradius, color, rotation, anchorname, lblsize, href, decoration))
        self._setsize()
        return self

    def side(self,
             side: Side = 'L',
             spacing: float = 0,
             pad: float = 0.5,
             leadlen: float = .5,
             label_ofst: float = 0.15,
             label_size: float = 14.,
             pinlabel_ofst: float = 0.05,
             pinlabel_size: float = 11.):
        ''' Set parameters for spacing/layout of one side

            Args:
                side: Side of box to define
                spacing: Distance between pins
                pad: Distance from box edge to first pin
                leadlen: Length of pin lead extensions
                label_ofst: Offset between box and label (inside box)
                label_size: Font size of label (inside box)
                pinlabel_ofst: Offset between box and pin label (outside box)
                pinlabel_size: Font size of pin label (outside box)
        '''
        side = cast(Side, side[0].upper())
        self.usersides[side] = IcSide(spacing, pad, leadlen,
                                      label_ofst, label_size,
                                      pinlabel_ofst, pinlabel_size)
        self._setsize()
        return self

    def _countpins(self) -> dict[Side, int]:
        ''' Count the number of pins (or slots) on each side '''
        pincount = {}
        for side, pins in self.pins.items():
            slotnames = [p.slot for p in pins]
            # Add a 0 - can't max an empty list
            slots = [int(p.split('/')[1]) for p in slotnames if p is not None] + [0]
            pincount[side] = max(len(pins), max(slots))
        return pincount

    def _autosize(self) -> None:
        ''' Determine size of box if not provided '''
        lengths: dict[str, float] = {}
        labelwidths: dict[str, float] = {}

        # Determine length of each side given spacing and pad
        for side in ['L', 'R', 'T', 'B']:
            side = cast(Side, side)
            sideparam = replace(self.usersides.get(side, self._dflt_side))
            self.sides[side] = sideparam
            if sideparam.spacing == 0:
                sideparam.spacing = 0.6
            lengths[side] = sideparam.pad * 2 + sideparam.spacing * (self.pincount[side] - 1)

            # Expand to fit pin labels if necessary
            labelw = 0.
            for p in self.pins[side]:
                if p.name:
                    lblsize = p.lblsize if p.lblsize else self.params['lsize']
                    labelw = max(labelw, text_size(p.name, size=lblsize)[0]/72*2)
            labelwidths[side] = labelw

        # Box is larger of the two sides, with minimum of 2
        labelw = labelwidths['L'] + labelwidths['R'] + 4*self.params['lofst']
        boxh = max(lengths.get('L', 0.), lengths.get('R', 0.), 2+self.params['edgepadH'])
        boxw = max(lengths.get('T', 0.), lengths.get('B', 0.), 2+self.params['edgepadW'], labelw)
        self._sizeauto = boxw, boxh

        d = min(boxw, boxh) * self.OFFSET_FACTOR
        # Adjust pad for the shorter of the two parallel sides
        for side in ['L', 'R']:
            side = cast(Side, side)
            sideparam = self.sides.get(side, self._dflt_side)
            sideparam.pad = (boxh - (2 * d) - sideparam.spacing * (self.pincount[side] - 1)) / 2

        for side in ['T', 'B']:
            side = cast(Side, side)
            sideparam = self.sides.get(side, self._dflt_side)
            sideparam.pad = (boxw - (2 * d) - sideparam.spacing * (self.pincount[side] - 1)) / 2

    def _autopinlayout(self) -> None:
        ''' Determine pin layout when box size is specified '''
        d = min(self.size[0], self.size[1]) * self.OFFSET_FACTOR
        for side in ['L', 'R', 'T', 'B']:
            side = cast(Side, side)
            sideparam = replace(self.usersides.get(side, self._dflt_side))
            self.sides[side] = sideparam
            length = self.size[0] if side in ['T', 'B'] else self.size[1]
            pad = sideparam.pad
            # pad = 0.1 * min(self.size[0], self.size[1])
            if sideparam.spacing == 0:
                #use PAD to evenly space pins over (length-2*pad)
                if self.pincount[side] > 1:
                    sideparam.spacing = (length - 2*pad - 2*d) / (self.pincount[side] - 1)
                else:
                    sideparam.pad = (length - 2*d)/2
            else:
                # Addjust PAD center the group of pins
                sideparam.pad = (length - sideparam.spacing*(self.pincount[side]-1) - 2*d) / 2

    def _drawbox(self) -> IcBox:
        ''' Draw main box and return its size '''
        if self.size:
            w, h = self.size
        elif self._sizeauto:
            w, h = self._sizeauto
        else:
            w, h = (2, 3)

        y1 = 0
        y2 = h
        path = [Point((0, 0)), Point((w, 0)), Point((w, h)), Point((0, h)), Point((0, 0))]
        self.segments.append(Segment(path))

        # 与外边框的距离
        radius = min(w, h) * self.OFFSET_FACTOR
        self.radius = radius
        # 内边框的矩形
        inner_path = [Point((radius, radius)), Point((w-radius, radius)), Point((w-radius, h-radius)), Point((radius, h-radius)), Point((radius, radius))]
        self.segments.append(Segment(inner_path))   

        return IcBox(w, h, y1, y2)

    def _pinpos(self, side: Side, pin: IcPin, num: int) -> Point:
        ''' Get XY position of pin '''
        d = min(self._icbox.w, self._icbox.h) * self.OFFSET_FACTOR
        sidesetup = self.sides.get(side, self._dflt_side)
        spacing = sidesetup.spacing if sidesetup.spacing > 0 else 0.6
        if pin.slot:
            num = int(pin.slot.split('/')[0]) - 1
        z = sidesetup.pad + num*spacing
        if pin.pos:
            z = sidesetup.pad + pin.pos * (self.pincount[side]-1)*spacing
        xy = {'L': Point((0, z + d)),
              'R': Point((self._icbox.w, z + d)),
              'T': Point((z + d, self._icbox.h)),
              'B': Point((z + d, 0))
              }.get(side, Point((0, 0)))

        # Adjust pin position for slant
        if side == 'T' and self.slant > 0:
            xy = Point((xy[0], xy[1] - xy[0] * math.tan(-math.radians(self.slant))))
        elif side == 'T' and self.slant < 0:
            xy = Point(((xy[0], xy[1] + (self._icbox.y2-self._icbox.h) - xy[0] * math.tan(-math.radians(self.slant)))))
        elif side == 'B' and self.slant < 0:
            xy = Point((xy[0], xy[1] - (self._icbox.y2-self._icbox.h) - xy[0] * math.tan(math.radians(self.slant))))
        elif side == 'B' and self.slant > 0:
            xy = Point((xy[0], xy[1] - xy[0] * math.tan(math.radians(self.slant))))
        return xy

    def _drawpin(self, side: Side, pin: IcPin, num: int) -> None:
        ''' Draw one pin and its labels '''
        # num is index of where pin is along side
        sidesetup = self.sides.get(side, self._dflt_side)
        xy = self._pinpos(side, pin, num)
        leadext = {'L': Point((-sidesetup.leadlen, 0)),
                   'R': Point((sidesetup.leadlen, 0)),
                   'T': Point((0, sidesetup.leadlen)),
                   'B': Point((0, -sidesetup.leadlen))}.get(side, Point((0, 0)))

        # Anchor
        anchorpos = xy+leadext
        self.anchors[f'in{side[0].upper()}{num+1}'] = anchorpos
        if pin.anchorname:
            self.anchors[pin.anchorname] = anchorpos
        elif pin.name:
            if pin.name == '>':
                self.anchors['CLK'] = anchorpos
            self.anchors[pin.name] = anchorpos
        if pin.pin:
            self.anchors[f'pin{pin.pin}'] = anchorpos

        # Lead        
        if sidesetup.leadlen > 0:
            if pin.invert:  # Add invert-bubble
                invertradius = pin.invertradius
                invertofst = {'L': Point((-invertradius, 0)),
                              'R': Point((invertradius, 0)),
                              'T': Point((0, invertradius)),
                              'B': Point((0, -invertradius))}.get(side, Point((0, 0)))
                self.segments.append(SegmentCircle(
                    xy+invertofst, invertradius))
                self.segments.append(Segment([xy+invertofst*2, xy+leadext]))
            else:
                self.segments.append(Segment([xy, xy+leadext]))

        # Pin Number (outside the box)
        if pin.pin and pin.pin != '':
            # Account for any invert-bubbles
            invertradius = pin.invertradius * pin.invert
            plbl = sidesetup.pinlabel_ofst
            pofst = {'L': Point((-plbl-invertradius*2, plbl)),
                     'R': Point((plbl+invertradius*2, plbl)),
                     'T': Point((plbl, plbl+invertradius*2)),
                     'B': Point((plbl, -plbl-invertradius*2))
                     }.get(side)

            align = cast(Optional[Tuple[Halign, Valign]],
                         {'L': ('right', 'bottom'),
                          'R': ('left', 'bottom'),
                          'T': ('left', 'bottom'),
                          'B': ('left', 'top')}.get(side))
            self.segments.append(SegmentText(
                pos=xy+pofst,
                label=pin.pin,
                align=align,
                fontsize=pin.pinlblsize if pin.pinlblsize is not None else sidesetup.pinlabel_size))

        if pin.name == '>':
            self._drawclkpin(xy, leadext, side, pin, num)
            return

        # Label (inside the box)
        if pin.name and pin.name != '':
            d = min(self._icbox.w, self._icbox.h) * self.OFFSET_FACTOR
            pofst = {'L': Point((sidesetup.label_ofst + d, 0)),
                     'R': Point((-sidesetup.label_ofst - d, 0)),
                     'T': Point((0, -sidesetup.label_ofst - d)),
                     'B': Point((0, sidesetup.label_ofst + d))}.get(side)

            align = cast(Optional[Tuple[Halign, Valign]],
                         {'L': ('left', 'center'),
                          'R': ('right', 'center'),
                          'T': ('center', 'top'),
                          'B': ('center', 'bottom')}.get(side))

            self.segments.append(SegmentText(
                pos=xy+pofst,
                label=pin.name,
                align=align,
                fontsize=pin.lblsize if pin.lblsize is not None else sidesetup.label_size,
                color=pin.color,
                rotation=pin.rotation,
                rotation_mode='default', href=pin.href, decoration=pin.decoration))
        
        # 矩形的大小也是 1/14 的短边长
        rect_h = self.RECT_H_FRAC * min(self._icbox.w, self._icbox.h)
        d = min(self._icbox.w, self._icbox.h) * self.OFFSET_FACTOR

        if side == 'L':
            # rectangle extends left from chip edge
            x0 = xy[0] + d
            y0 = xy[1] - rect_h / 2
            y1 = xy[1] + rect_h / 2
            rect_pts = [Point((xy[0], y1)), Point((x0, y1)), Point((x0, y0)), Point((xy[0], y0))]
        elif side == 'R':
            x0 = xy[0] - d
            y0 = xy[1] - rect_h / 2
            y1 = xy[1] + rect_h / 2
            rect_pts = [Point((xy[0], y1)), Point((x0, y1)), Point((x0, y0)), Point((xy[0], y0))]
        elif side == 'T':
            x0 = xy[0] - rect_h / 2
            y0 = xy[1]
            rect_pts = [Point((x0, y0)), Point((x0, y0 - d)), Point((x0 + rect_h, y0 - d)), Point((x0 + rect_h, y0))]
        else:  # 'B'
            x0 = xy[0] - rect_h / 2
            y0 = xy[1]
            rect_pts = [Point((x0, y0)), Point((x0, y0 + d)), Point((x0 + rect_h, y0 + d)), Point((x0 + rect_h, y0))]

        # draw rectangle
        self.segments.append(Segment(rect_pts))

    def _drawclkpin(self, xy: Point, leadext: Point,
                    side: Side, pin: IcPin, num: int) -> None:
        ''' Draw clock pin > '''
        sidesetup = self.sides.get(side, self._dflt_side)
        sidesetup.label_size
        clkw, clkh = 0.4 * sidesetup.label_size/16, 0.2 * sidesetup.label_size/16
        if side in ['T', 'B']:
            clkw = math.copysign(clkw, leadext[1]) if leadext[1] != 0 else clkw
            clkpath = [Point((xy[0]-clkh, xy[1])),
                        Point((xy[0], xy[1]-clkw)),
                        Point((xy[0]+clkh, xy[1]))]
        else:
            clkw = math.copysign(clkw, -leadext[0]) if leadext[0] != 0 else clkw
            clkpath = [Point((xy[0], xy[1]+clkh)),
                        Point((xy[0]+clkw, xy[1])),
                        Point((xy[0], xy[1]-clkh))]
        self.segments.append(Segment(clkpath))

    def _drawpins(self) -> None:
        ''' Draw all the pins '''
        for side, pins in self.pins.items():
            for i, pin in enumerate(pins):
                self._drawpin(side, pin, i)

    def _setsize(self) -> None:
        ''' Set size based on pins added so far '''
        self.pincount = self._countpins()
        if self.size is None:
            self._autosize()
        else:
            self._autopinlayout()
        self.pinspacing = {'L': self.sides['L'].spacing,
                           'R': self.sides['R'].spacing,
                           'T': self.sides['T'].spacing,
                           'B': self.sides['B'].spacing}

    def _place(self, dwgxy: XY, dwgtheta: float, **dwgparams) -> tuple[Point, float]:
        self._icbox = self._drawbox()
        self._drawpins()
        self.elmparams['lblloc'] = 'center'
        self.anchors['center'] = (self._icbox.w/2, self._icbox.h/2)
        return super()._place(dwgxy, dwgtheta, **dwgparams)


def test_aic_fixed():

    with schemdraw.Drawing() as d:
        d.config(fontsize=12)
        T = (AIc()
            .side('L', spacing=1.5, pad=1.5, leadlen=1)
            .side('R', spacing=2)
            .side('T', pad=1.5, spacing=1)
            .pin(name='TRG', side='left', pin='2')
            .pin(name='THR', side='left', pin='6')
            .pin(name='DIS', side='left', pin='7')
            .pin(name='CTL', side='right', pin='5')
            .pin(name='OUT', side='right', pin='3')
            .pin(name='RST', side='top', pin='4')
            .pin(name='Vcc', side='top', pin='8')
            .pin(name='GND', side='bot', pin='1')
            .label('555'))
        BOT = elm.Ground().at(T.GND)
        elm.Dot()
        elm.Resistor().endpoints(T.DIS, T.THR).label('Rb').idot()
        elm.Resistor().up().at(T.DIS).label('Ra').label('+Vcc', 'right')
        elm.Line().endpoints(T.THR, T.TRG)
        elm.Capacitor().at(T.TRG).toy(BOT.start).label('C')
        elm.Line().tox(BOT.start)
        elm.Capacitor().at(T.CTL).toy(BOT.start).label(r'.01$\mu$F', 'bottom').dot()
        elm.Dot().at(T.DIS)
        elm.Dot().at(T.THR)
        elm.Dot().at(T.TRG)
        elm.Line().endpoints(T.RST,T.Vcc).dot()
        elm.Line().up(d.unit/4).label('+Vcc', 'right')
        elm.Resistor().right().at(T.OUT).label('330')
        elm.LED().flip().toy(BOT.start)
        elm.Line().tox(BOT.start)


test_aic_fixed()