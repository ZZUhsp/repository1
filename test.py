from schemdraw.elements.intcircuits import *
import schemdraw.elements as elm
from schemdraw import Drawing

import matplotlib.pyplot as plt


class OIc(Element):
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

    def __init__(self,
                 size: Optional[XY] = None,
                 pins: Optional[Sequence[IcPin]] = None,
                 slant: float = 0,
                 **kwargs):
        super().__init__(**kwargs)
        self.size = size if size is not None else self.params.get('size')
        # 存储自定义的大小
        self._sizeauto: Optional[tuple[float, float]] = None
        self.slant = slant
        self.pins: dict[Side, list[IcPin]] = {'L': [], 'R': [], 'T': [], 'B': []}
        # 存储用户自定义的每边布局参数
        self.usersides: dict[Side, IcSide] = {}
        self.sides: dict[Side, IcSide] = {}
        # 包含所有侧面默认布局参数 如引脚间距、引线长度、标签偏移量和大小
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

        self._icbox = IcBox(0, 0, 0, 0)
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

    # compute size
    def _autosize(self) -> None:
        """Auto compute full box size and set spacing/pad so pins are inside usable minus margin."""
        side_needed = {}
        labelwidths = {'L': 0., 'R': 0., 'T': 0., 'B': 0.}
        for s in ['L', 'R', 'T', 'B']:
            sideparam = replace(self.usersides.get(s, self._dflt_side))
            self.sides[cast(Side, s)] = sideparam
            if sideparam.spacing == 0:
                sideparam.spacing = 0.0
            needed = sideparam.pad * 2 + sideparam.spacing * max(0, (self.pincount[s] - 1))
            side_needed[s] = needed
            maxlabel = 0.
            for p in self.pins[s]:
                if p.name:
                    lblsize = p.lblsize if p.lblsize else self.params['lsize']
                    maxlabel = max(maxlabel, text_size(p.name, size=lblsize)[0] / 72 * 2)
            labelwidths[s] = maxlabel

        usable_TB_needed = max(side_needed['T'], side_needed['B'], labelwidths['L'] + labelwidths['R'] + 4 * self.params['lofst'])
        usable_LR_needed = max(side_needed['L'], side_needed['R'])

        # initial guess to avoid circular d dependence
        w_guess = max(usable_TB_needed, 2.0)
        h_guess = max(usable_LR_needed, 2.0)
        d_guess = 0.15 * min(w_guess, h_guess)

        w = usable_TB_needed + 2 * d_guess
        h = usable_LR_needed + 2 * d_guess
        d = 0.15 * min(w, h)
        w = max(usable_TB_needed + 2 * d, 2.0)
        h = max(usable_LR_needed + 2 * d, 2.0)
        self._sizeauto = (w, h)

        usable_w = max(0.0, w - 2 * d)
        usable_h = max(0.0, h - 2 * d)

        # default margin: a fractin of the short side
        base_margin = 0.07 * min(w, h)
        for s in ['L', 'R']:
            sp = self.sides[cast(Side, s)]
            n = self.pincount[s]
            usable = usable_h
            margin = min(base_margin, usable / 2.0)
            if n <= 0:
                sp.pad = usable / 2.0
                sp.spacing = 0.0
            elif n == 1:
                sp.pad = usable / 2.0
                sp.spacing = 0.0
            else:
                # 若用户没有指定 spacing，均匀分布在 [margin, usable-margin]
                if sp.spacing == 0.0:
                    sp.spacing = max(0.0, (usable - 2 * margin) / (n - 1))
                    sp.pad = margin
                else:
                    total_span = sp.spacing * (n - 1)
                    if total_span > usable:
                        # 缩放 spacing 到可用范围
                        sp.spacing = usable / (n - 1)
                        sp.pad = 0.0
                    else:
                        sp.pad = (usable - total_span) / 2.0

        for s in ['T', 'B']:
            sp = self.sides[cast(Side, s)]
            n = self.pincount[s]
            usable = usable_w
            margin = min(base_margin, usable / 2.0)
            if n <= 0:
                sp.pad = usable / 2.0
                sp.spacing = 0.0
            elif n == 1:
                sp.pad = usable / 2.0
                sp.spacing = 0.0
            else:
                if sp.spacing == 0.0:
                    sp.spacing = max(0.0, (usable - 2 * margin) / (n - 1))
                    sp.pad = margin
                else:
                    total_span = sp.spacing * (n - 1)
                    if total_span > usable:
                        sp.spacing = usable / (n - 1)
                        sp.pad = 0.0
                    else:
                        sp.pad = (usable - total_span) / 2.0

    def _autopinlayout(self) -> None:
        """When size explicitly provided: distribute pins inside [margin, usable-margin]."""
        w, h = self.size
        d = 0.15 * min(w, h)
        usable_w = max(0.0, w - 2 * d)
        usable_h = max(0.0, h - 2 * d)
        base_margin = 0.07 * min(w, h)

        for side in ['L', 'R', 'T', 'B']:
            s = cast(Side, side)
            sideparam = replace(self.usersides.get(s, self._dflt_side))
            self.sides[s] = sideparam
            n = self.pincount[side]
            usable = usable_w if side in ('T', 'B') else usable_h
            margin = min(base_margin, usable / 2.0)

            if n <= 0:
                sideparam.pad = usable / 2.0
                sideparam.spacing = 0.0
            elif n == 1:
                sideparam.pad = usable / 2.0
                sideparam.spacing = 0.0
            else:
                if sideparam.spacing == 0 or sideparam.spacing is None:
                    sideparam.spacing = max(0.0, (usable - 2 * margin) / (n - 1))
                    sideparam.pad = margin
                else:
                    total_span = sideparam.spacing * (n - 1)
                    if total_span > usable:
                        sideparam.spacing = usable / (n - 1)
                        sideparam.pad = 0.0
                    else:
                        sideparam.pad = (usable - total_span) / 2.0

    def _drawbox(self) -> IcBox:
        ''' Draw main box and return its size '''
        if self.size:
            w, h = self.size
        elif self._sizeauto:
            w, h = self._sizeauto
        else:
            w, h = (2, 3)

        # 斜边的缩进
        d = 0.15 * min(w, h)
        path = [
            Point((d, 0)),
            Point((w - d, 0)),
            Point((w, d)),
            Point((w, h - d)),
            Point((w - d, h)),
            Point((d, h)),
            Point((0, h - d)),
            Point((0, d)),
            Point((d, 0)),
        ]
        # 根据路径填充
        self.segments.append(Segment(path))

        last_inner = None
        # 画内八边形
        for i in range(2):
            if i == 0:
                offset = 0.0244 * min(w, h)
            else:
                offset = 0.0427 * min(w, h)
            # offset = (i+1) * 0.2
            w_i = w - 2 * offset
            h_i = h - 2 * offset
            if w_i <= 0 or h_i <= 0:
                break
            d_i = 0.15 * min(w_i, h_i)
            x0 = offset
            y0 = offset
            pts_i = [
                Point((x0 + d_i, y0)),
                Point((x0 + w_i - d_i, y0)),
                Point((x0 + w_i, y0 + d_i)),
                Point((x0 + w_i, y0 + h_i - d_i)),
                Point((x0 + w_i - d_i, y0 + h_i)),
                Point((x0 + d_i, y0 + h_i)),
                Point((x0, y0 + h_i - d_i)),
                Point((x0, y0 + d_i)),
                Point((x0 + d_i, y0)),
            ]
            # 你可以设置不同的 stroke width / color
            self.segments.append(Segment(pts_i))
            last_inner = (x0, y0, w_i, h_i)

        if last_inner is not None:
            self._inner_box = last_inner
        else:
            self._inner_box = None

        return IcBox(w, h, 0, h)

    def _pinpos(self, side: Side, pin: IcPin, num: int) -> Point:
        sidesetup = self.sides.get(side, self._dflt_side)
        spacing = sidesetup.spacing if sidesetup.spacing > 0 else 0.0

        if pin.slot:
            num = int(pin.slot.split('/')[0]) - 1

        w = self._icbox.w
        h = self._icbox.h
        d = 0.15 * min(w, h)
        usable_len = (w - 2 * d) if side in ('T', 'B') else (h - 2 * d)

        # compute margin consistent with layout stage
        base_margin = 0.07 * min(w, h)
        margin = min(base_margin, usable_len / 2.0)

        if self.pincount[side] <= 1:
            z = usable_len / 2.0
        else:
            if pin.pos is not None:
                frac = max(0.0, min(1.0, pin.pos))
                # map pos into [margin, usable-margin]
                z = margin + frac * max(0.0, (usable_len - 2 * margin))
            else:
                # use computed pad and spacing (pad might be margin or centered pad)
                z = sidesetup.pad + num * spacing

        # clamp to avoid overflow
        z = max(0.0, min(z, usable_len))

        if side == 'L':
            return Point((0, d + z))
        elif side == 'R':
            return Point((w, d + z))
        elif side == 'T':
            return Point((d + z, h))
        elif side == 'B':
            return Point((d + z, 0))
        else:
            return Point((0, 0))

    def _drawpin(self, side: Side, pin: IcPin, num: int) -> None:
        ''' Draw one pin and its labels '''
        # num is index of where pin is along side
        sidesetup = self.sides.get(side, self._dflt_side)
        xy = self._pinpos(side, pin, num)
        # 引脚所在的边向外延伸的向量
        leadext = {'L': Point((-sidesetup.leadlen, 0)),
                   'R': Point((sidesetup.leadlen, 0)),
                   'T': Point((0, sidesetup.leadlen)),
                   'B': Point((0, -sidesetup.leadlen))}.get(side, Point((0, 0)))

        # Anchor
        anchorpos = xy + leadext
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
            if pin.invert:  # Add invert-bubble 倒相起泡
                invertradius = pin.invertradius  # 倒相起泡的半径
                invertofst = {'L': Point((-invertradius, 0)),
                              'R': Point((invertradius, 0)),
                              'T': Point((0, invertradius)),
                              'B': Point((0, -invertradius))}.get(side, Point((0, 0)))
                # 画一个圆 圆心为xy+invertofst 半径invertradius
                self.segments.append(SegmentCircle(
                    xy + invertofst, invertradius))
                self.segments.append(Segment([xy + invertofst * 2, xy + leadext]))
            else:
                # 普通引脚 画一个线即可
                self.segments.append(Segment([xy, xy + leadext]))

        # Pin Number
        if pin.pin and pin.pin != '':
            # Account for any invert-bubbles
            invertradius = pin.invertradius * pin.invert
            # 引脚标签的偏移量
            plbl = sidesetup.pinlabel_ofst
            pofst = {'L': Point((-plbl - invertradius * 2, plbl)),
                     'R': Point((plbl + invertradius * 2, plbl)),
                     'T': Point((plbl, plbl + invertradius * 2)),
                     'B': Point((plbl, -plbl - invertradius * 2))
                     }.get(side)

            # 设置文本的对齐方式
            align = cast(Optional[Tuple[Halign, Valign]],
                         {'L': ('right', 'bottom'),
                          'R': ('left', 'bottom'),
                          'T': ('left', 'bottom'),
                          'B': ('left', 'top')}.get(side))
            self.segments.append(SegmentText(
                pos=xy + pofst,
                label=pin.pin,
                align=align,
                fontsize=pin.pinlblsize if pin.pinlblsize is not None else sidesetup.pinlabel_size))

        if pin.name == '>':
            # 绘制时钟引脚
            self._drawclkpin(xy, leadext, side, pin, num)
            return

        # Label (inside the box)
        if pin.name and pin.name != '':
            pofst = {'L': Point((sidesetup.label_ofst, 0)),
                     'R': Point((-sidesetup.label_ofst, 0)),
                     'T': Point((0, -sidesetup.label_ofst)),
                     'B': Point((0, sidesetup.label_ofst))}.get(side)
            
            target = xy + pofst
            inner = getattr(self, '_inner_box', None)

            if inner is not None:
                x0, y0, wi, hi = inner
                # 安全边距
                inner_margin = 0.01 * min(self._icbox.w, self._icbox.h)

                min_x = x0 + inner_margin
                max_x = x0 + wi - inner_margin
                min_y = y0 + inner_margin
                max_y = y0 + hi - inner_margin

                # clamp target 到内盒范围（同时保留 pofst 的侧向语义）
                tx = max(min_x, min(max_x, target[0]))
                ty = max(min_y, min(max_y, target[1]))
                target = Point((tx, ty))

                # 自动缩放字号（如果文字宽度比可用宽度大）
                lblsize = pin.lblsize if pin.lblsize is not None else sidesetup.label_size
                try:
                    txt_w = text_size(pin.name, size=lblsize)[0] / 72 * 2
                except Exception:
                    txt_w = 0.0
                # 可用宽度：内盒宽度减掉左右留白
                allowed_w = max(0.0, (max_x - min_x) - 2 * self.params.get('lofst', 0.15))
                if allowed_w > 0 and txt_w > 0 and txt_w > allowed_w:
                    scale = allowed_w / txt_w
                    newsize = max(6, int(lblsize * scale))  # 最小字号限制
                else:
                    newsize = lblsize
            else:
                # 没有内盒信息则不约束
                newsize = pin.lblsize if pin.lblsize is not None else sidesetup.label_size


            align = cast(Optional[Tuple[Halign, Valign]],
                         {'L': ('left', 'center'),
                          'R': ('right', 'center'),
                          'T': ('center', 'top'),
                          'B': ('center', 'bottom')}.get(side))

            self.segments.append(SegmentText(
                pos=target,
                label=pin.name,
                align=align,
                fontsize=newsize,
                color=pin.color,
                rotation=pin.rotation,
                rotation_mode='default', href=pin.href, decoration=pin.decoration))

        # 绘制边框内的矩形逻辑
        if sidesetup.spacing > 0:
            rect_h = min(sidesetup.spacing * 0.8, 0.045 * min(self._icbox.w, self._icbox.h))
        else:
            rect_h = 0.045 * min(self._icbox.w, self._icbox.h)

        d = 0.024 * min(self._icbox.w, self._icbox.h)

        if side == 'L':
            # rectangle extends left from chip edge
            x0 = xy[0] + d
            y0 = xy[1] - rect_h / 2
            y1 = xy[1] + rect_h / 2
            rect_pts = [Point((xy[0], y1)), Point((x0, y1)), Point((x0, y0)), Point((xy[0], y0))]
            # anchorpos = Point((x0, y0 + rect_h/2))  # 外侧中点
        elif side == 'R':
            x0 = xy[0] - d
            y0 = xy[1] - rect_h / 2
            y1 = xy[1] + rect_h / 2
            rect_pts = [Point((xy[0], y1)), Point((x0, y1)), Point((x0, y0)), Point((xy[0], y0))]
            # anchorpos = Point((x0 + rect_ext, y0 + rect_h/2))
        elif side == 'T':
            x0 = xy[0] - rect_h / 2
            y0 = xy[1]
            rect_pts = [Point((x0, y0)), Point((x0, y0 - d)), Point((x0 + rect_h, y0 - d)), Point((x0 + rect_h, y0))]
            # anchorpos = Point((x0 + rect_h/2, y0 + rect_ext))
        else:  # 'B'
            x0 = xy[0] - rect_h / 2
            y0 = xy[1]
            rect_pts = [Point((x0, y0)), Point((x0, y0 + d)), Point((x0 + rect_h, y0 + d)), Point((x0 + rect_h, y0))]
            # anchorpos = Point((x0 + rect_h/2, y0))

        self.segments.append(Segment(rect_pts))

    def _drawclkpin(self, xy: Point, leadext: Point,
                    side: Side, pin: IcPin, num: int) -> None:
        ''' Draw clock pin > '''
        sidesetup = self.sides.get(side, self._dflt_side)
        sidesetup.label_size
        clkw, clkh = 0.4 * sidesetup.label_size / 16, 0.2 * sidesetup.label_size / 16
        if side in ['T', 'B']:
            clkw = math.copysign(clkw, leadext[1]) if leadext[1] != 0 else clkw
            clkpath = [Point((xy[0] - clkh, xy[1])),
                       Point((xy[0], xy[1] - clkw)),
                       Point((xy[0] + clkh, xy[1]))]
        else:
            clkw = math.copysign(clkw, -leadext[0]) if leadext[0] != 0 else clkw
            clkpath = [Point((xy[0], xy[1] + clkh)),
                       Point((xy[0] + clkw, xy[1])),
                       Point((xy[0], xy[1] - clkh))]
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
        self.anchors['center'] = (self._icbox.w / 2, self._icbox.h / 2)
        return super()._place(dwgxy, dwgtheta, **dwgparams)
    

def test_ic_fixed():
    ic = OIc(size = (10, 10), pins=[
        elm.intcircuits.IcPin(side='L', name='IN1', pin='1'),
        elm.intcircuits.IcPin(side='L', name='IN2', pin='2'),
        elm.intcircuits.IcPin(side='L', name='IN3', pin='3'),
        elm.intcircuits.IcPin(side='R', name='OUT1', pin='7'),
        elm.intcircuits.IcPin(side='R', name='OUT2', pin='8'),
        elm.intcircuits.IcPin(side='R', name='OUT3', pin='9'),
        elm.intcircuits.IcPin(side='R', name='OUT4', pin='10'),
        elm.intcircuits.IcPin(side='R', name='OUT5', pin='11'),
        elm.intcircuits.IcPin(side='R', name='OUT5', pin='12'),
        elm.intcircuits.IcPin(side='T', name='VCC', pin='14'),
        elm.intcircuits.IcPin(side='B', name='GND', pin='G'),
    ]).label('MyChipFixed')
    
    # draw and save
    with Drawing() as d:
        d += ic
        fig = d.draw()   # 返回 matplotlib Figure
        plt.show()       # 在 Console 里显示

test_ic_fixed()