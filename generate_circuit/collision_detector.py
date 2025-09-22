"""
第二部分：碰撞检测器
在第一部分的基础上，添加碰撞检测算法，确保器件不重叠
调整器件位置以避免碰撞
"""
import json
import math
from schemdraw import Drawing
import schemdraw.elements as elm
from typing import Dict, List, Tuple, Any
from json_reader_and_drawer import JsonReaderAndDrawer
import os
from PIL import Image, ImageDraw


class CollisionDetector:
    def __init__(self, reader_drawer: JsonReaderAndDrawer):
        """初始化碰撞检测器"""
        self.reader_drawer = reader_drawer
        self.chip_info = reader_drawer.get_chip_info()
        self.component_info = reader_drawer.get_component_info()
        self.adjusted_positions = {}  # 调整后的位置信息

    def _check_bbox_collision(self, bbox1: Dict, bbox2: Dict, margin: float = 1.0) -> bool:
        """检查两个bounding box是否重叠（加上安全边距）"""
        return not (bbox1['x_max'] + margin < bbox2['x_min'] or
                    bbox2['x_max'] + margin < bbox1['x_min'] or
                    bbox1['y_max'] + margin < bbox2['y_min'] or
                    bbox2['y_max'] + margin < bbox1['y_min'])

    def _check_collision_with_chip(self, bbox: Dict, margin: float = 2.0) -> bool:
        """检查组件是否与芯片重叠"""
        chip_bbox = self.chip_info['bbox']
        chip_bbox_with_margin = {
            'x_min': chip_bbox['x_min'] - margin,
            'x_max': chip_bbox['x_max'] + margin,
            'y_min': chip_bbox['y_min'] - margin,
            'y_max': chip_bbox['y_max'] + margin
        }
        return self._check_bbox_collision(bbox, chip_bbox_with_margin, 0)

    def _create_bbox_from_position(self, x: float, y: float, width: float, height: float) -> Dict:
        """根据位置和尺寸创建bounding box"""
        return {
            'x_min': x - width/2, 'x_max': x + width/2,
            'y_min': y - height/2, 'y_max': y + height/2,
            'width': width, 'height': height
        }

    def _get_pin_position_on_chip(self, pin_number: int) -> Tuple[str, float]:
        """获取引脚在芯片上的位置信息"""
        # 基于555芯片的引脚配置
        pin_configs = {
            1: ('bot', 0.0),    # GND
            2: ('left', 0.5),   # THR
            3: ('right', 0.0),  # OUT
            4: ('top', -0.5),   # RST
            5: ('right', 1.0),  # CTL
            6: ('left', -0.5),  # TRG
            7: ('left', 1.0),   # DIS
            8: ('top', 0.5),    # Vcc
            9: ('right', -1.0)  # Vdd
        }
        return pin_configs.get(pin_number, ('right', 0.0))

    def _calculate_optimal_position(self, component_id: str) -> Tuple[float, float]:
        """根据连接关系计算组件的最优位置"""
        component = self.component_info[component_id]
        connected_pins = component['connected_pins']

        if not connected_pins:
            return (2.0, 2.0)  # 默认位置

        # 计算平均位置
        total_x, total_y = 0.0, 0.0
        for pin in connected_pins:
            side, offset = self._get_pin_position_on_chip(pin)

            # 根据引脚位置计算组件应该放置的位置
            if side == 'left':
                x, y = -3.0, offset * 1.5
            elif side == 'right':
                x, y = 3.0, offset * 1.5
            elif side == 'top':
                x, y = offset * 1.5, 2.5
            elif side == 'bot':
                x, y = offset * 1.5, -2.5
            else:
                x, y = 2.0, 2.0

            total_x += x
            total_y += y

        # 返回平均位置
        avg_x = total_x / len(connected_pins)
        avg_y = total_y / len(connected_pins)

        return (avg_x, avg_y)

    def _adjust_position_to_avoid_collision(self, component_id: str) -> Tuple[float, float]:
        """调整位置以避免与已放置的组件和芯片发生碰撞"""
        component = self.component_info[component_id]
        width = component['width']
        height = component['height']

        # 获取期望位置
        x, y = self._calculate_optimal_position(component_id)

        max_attempts = 50
        search_radius = 1.0

        for attempt in range(max_attempts):
            # 创建当前位置的bounding box
            test_bbox = self._create_bbox_from_position(x, y, width, height)

            # 检查与芯片的碰撞
            has_collision = self._check_collision_with_chip(test_bbox)

            # 检查与已放置组件的碰撞
            if not has_collision:
                for placed_comp_id, placed_info in self.adjusted_positions.items():
                    if placed_comp_id == component_id:
                        continue

                    placed_bbox = self._create_bbox_from_position(
                        placed_info['position'][0], placed_info['position'][1],
                        placed_info['width'], placed_info['height']
                    )

                    if self._check_bbox_collision(test_bbox, placed_bbox):
                        has_collision = True
                        break

            # 如果没有碰撞，返回当前位置
            if not has_collision:
                if attempt > 0:
                    print(f"    经过 {attempt} 次调整，避免了碰撞")
                return x, y

            # 使用系统的搜索策略
            if attempt == 0:
                # 记录原始期望位置
                original_x, original_y = self._calculate_optimal_position(
                    component_id)

            if attempt < 8:
                # 前8次尝试：8个主要方向
                angle = attempt * 45
                radius = search_radius
            else:
                # 后续尝试：螺旋式搜索
                angle = (attempt * 30) % 360
                radius = search_radius * (1 + (attempt - 8) * 0.5)

            x_offset = radius * math.cos(math.radians(angle))
            y_offset = radius * math.sin(math.radians(angle))

            x = original_x + x_offset
            y = original_y + y_offset

        # 如果仍然找不到位置，尝试远离芯片的位置
        print(f"    尝试将组件 {component_id} 放置在更远的位置")
        connected_pins = component['connected_pins']
        if connected_pins:
            pin = connected_pins[0]
            side, offset = self._get_pin_position_on_chip(pin)

            if side == 'left':
                x, y = -10.0, offset * 3.0
            elif side == 'right':
                x, y = 10.0, offset * 3.0
            elif side == 'top':
                x, y = offset * 3.0, 8.0
            elif side == 'bot':
                x, y = offset * 3.0, -8.0
            else:
                x, y = 10.0, 6.0
        else:
            x, y = 10.0, 6.0  # 默认远离位置

        print(f"    警告: 将组件 {component_id} 放置在远离位置 ({x:.1f}, {y:.1f})")
        return x, y

    def detect_and_resolve_collisions(self):
        """检测并解决所有碰撞"""
        print("开始碰撞检测和位置调整...")

        # 按连接的重要性排序组件（连接引脚多的优先）
        sorted_components = sorted(
            self.component_info.items(),
            key=lambda x: len(x[1]['connected_pins']),
            reverse=True
        )

        for comp_id, component in sorted_components:
            print(f"处理组件 {comp_id} ({component['type']})...")

            # 调整位置以避免重叠
            adjusted_x, adjusted_y = self._adjust_position_to_avoid_collision(
                comp_id)

            print(f"组件 {comp_id} 调整后位置: ({adjusted_x:.2f}, {adjusted_y:.2f})")

            # 更新调整后的位置信息
            self.adjusted_positions[comp_id] = {
                'position': (adjusted_x, adjusted_y),
                'type': component['type'],
                'label': component['label'],
                'width': component['width'],
                'height': component['height'],
                'connected_pins': component['connected_pins'],
                'bbox': self._create_bbox_from_position(
                    adjusted_x, adjusted_y, component['width'], component['height']
                )
            }

        print("碰撞检测和位置调整完成")
        return self.adjusted_positions

    def create_adjusted_elements(self):
        """根据调整后的位置创建新的schemdraw元素"""
        print("根据调整后的位置创建元素...")

        adjusted_elements = {}

        for comp_id, position_info in self.adjusted_positions.items():
            component = self.reader_drawer.components[comp_id]
            comp_type = component['type']
            label = position_info['label']
            position = position_info['position']

            # 获取schemdraw元素类
            ElementClass = self.reader_drawer._get_schemdraw_element_class(
                comp_type)

            # 获取schemdraw参数
            schemdraw_params = component.get('schemdraw_params', {})

            try:
                if comp_type == 'voltage_source':
                    element = elm.SourceV().at(position)
                    element = self.reader_drawer._apply_schemdraw_params_safely(
                        element, schemdraw_params, [], comp_type)
                    if label.strip():
                        element = element.label(label, 'top')

                elif comp_type == 'resistor':
                    element = ElementClass().at(position)
                    element = self.reader_drawer._apply_schemdraw_params_safely(
                        element, schemdraw_params, ['length', 'theta'], comp_type)
                    if label.strip():
                        element = element.label(label, 'top')

                elif comp_type == 'capacitor':
                    element = ElementClass().at(position)
                    element = self.reader_drawer._apply_schemdraw_params_safely(
                        element, schemdraw_params, ['length', 'theta', 'width'], comp_type)
                    if label.strip():
                        element = element.label(label, 'bottom')

                elif comp_type == 'LED':
                    element = ElementClass().at(position)
                    element = self.reader_drawer._apply_schemdraw_params_safely(
                        element, schemdraw_params, ['length', 'theta', 'width'], comp_type)
                    if label.strip():
                        element = element.label(label, 'right')

                elif comp_type == 'ground':
                    element = elm.Ground().at(position)

                else:
                    element = ElementClass().at(position)
                    element = self.reader_drawer._apply_schemdraw_params_safely(
                        element, schemdraw_params, [], comp_type)
                    if label.strip():
                        element = element.label(label)

                adjusted_elements[comp_id] = {
                    'element': element,
                    'position': position,
                    'type': comp_type,
                    'label': label
                }
                print(f"    成功创建调整后的组件 {comp_id}")

            except Exception as e:
                print(f"    创建调整后的组件 {comp_id} 时出错: {e}")

        return adjusted_elements

    def _apply_type_adjustment(self, orig_bbox, elem_classname):
        """
        根据元素类别对原始 global bbox 做调整（units）。
        输入 orig_bbox = (exmin, eymin, exmax, eymax)
        返回 adjusted_bbox = (axmin, aymin, axmax, aymax)
        """
        exmin, eymin, exmax, eymax = orig_bbox
        name = elem_classname.lower()
        print(f"Element class: {elem_classname}")
        # 默认不变
        axmin, aymin, axmax, aymax = exmin, eymin, exmax, eymax

        if 'resistor' in name:
            print("Adjusting resistor bbox")
            axmin = exmin + 0.45
            axmax = exmax - 0.45
            aymin = eymin - 0.05
            aymax = eymax + 0.05
        elif 'capacitor' in name:
            print("Adjusting capacitor bbox")
            axmin = exmin + 0.7
            axmax = exmax - 0.7
            aymin = eymin - 0.1
            aymax = eymax + 0.1
        elif 'ground' in name or 'gnd' in name:
            print("Adjusting ground bbox")
            axmin = exmin - 0.05
            axmax = exmax + 0.05
            aymin = eymin - 0.05
            aymax = eymax - 0.3
        elif 'ic' in name:
            print("Adjusting box/rectangle bbox")
            axmin = exmin + 0.4
            axmax = exmax - 0.4
            aymin = eymin + 0.4
            aymax = eymax - 0.4
        # 你还可以在这里加入更多元件类型的规则

        # 防护：如果调整后反转（xmin >= xmax 或 ymin >= ymax），则退回原始 bbox
        if not (axmin < axmax and aymin < aymax):
            return (exmin, eymin, exmax, eymax)
        return (axmin, aymin, axmax, aymax)

    def get_component_info_box(self, drawings):
        """
        获取每个元件的边界框信息（units），并计算相对于画布左上角的相对 bbox（units）。
        返回结构：
        {
        'drawing_bbox_units': (xmin,ymin,xmax,ymax),
        'components': {
            name: {'global_bbox_units': (...), 'relative_bbox_units': (...), 'center_units': (...)}
        }
        }
        """
        if not drawings.elements:
            return {'drawing_bbox_units': (0,0,0,0), 'components': {}}

        d_bbox = drawings.get_bbox()
        xmin_global, ymin_global, xmax_global, ymax_global = d_bbox

        xmin_global -= 0.1
        ymin_global -= 0.1
        ymax_global += 0.1
        xmax_global += 0.1

        print(f"整个图纸的全局边界框 (xmin, ymin, xmax, ymax): {d_bbox}\n")

        components_info = {}
        for idx, element in enumerate(drawings.elements):
            # 使用 element.name 作为 label，如果没有则自动命名
            name = getattr(element, 'name', None)
            if not name:
                name = f"elem_{idx}"

            # 获取元素 bbox（transform=True => 全局坐标）
            try:
                element_bbox_global = element.get_bbox(transform=True)
            except Exception as e:
                components_info[name] = {
                    'global_bbox_units': None,
                    'relative_bbox_units': None,
                    'center_units': None,
                    'error': str(e)
                }
                continue

            exmin, eymin, exmax, eymax = element_bbox_global
            # 应用类型调整
            # exmin, eymin, exmax, eymax = self._apply_type_adjustment(element_bbox_global, element.__class__.__name__)

            # 计算中心（units）
            center_x = (exmin + exmax) / 2.0
            center_y = (eymin + eymax) / 2.0

            # 转为相对左上角坐标（units），Y 向下为正
            rel_xmin = exmin - xmin_global
            rel_xmax = exmax - xmin_global
            rel_ymin = ymax_global - eymax
            rel_ymax = ymax_global - eymin

            # 相对于左上角的中心（units）
            rel_center_x = center_x - xmin_global
            rel_center_y = ymax_global - center_y  # 翻转 Y 轴到“向下为正”的图像坐标系

            components_info[name] = {
                'global_bbox_units': element_bbox_global,
                'relative_bbox_units': (rel_xmin, rel_ymin, rel_xmax, rel_ymax),
                'center_units': (center_x, center_y),
                'relative_center_units': (rel_center_x, rel_center_y)
            }

        return {'drawing_bbox_units': d_bbox, 'components': components_info}

    def _find_content_bbox(self, img, bg_thresh=250):
        gray = img.convert('L')
        bw = gray.point(lambda p: 0 if p < bg_thresh else 255, mode='L')
        bbox = bw.getbbox()
        if bbox is None:
            return (0, 0, img.width, img.height)
        return bbox


    def draw_collision_free_circuit(self, output_file='collision_free_circuit.png', json_out='components_bbox.json', dpi=200):
        """
        绘制并保存电路图，同时把每个元件的 bbox、type、label 一并保存到 json_out。
        返回 (output_file, out_bbox_img, json_out)
        """
        print(f"正在绘制避免碰撞的电路图到 {output_file}...")

        adjusted_elements = self.create_adjusted_elements()

        # inserted 存 (label, element, type)
        inserted = []

        from schemdraw import Drawing
        with Drawing(file=output_file, transparent=False) as d:
            d.config(fontsize=10)
            d.config(unit=1.6)

            # 添加芯片（IC）
            if getattr(self.reader_drawer, 'ic_element', None):
                ic_elem = self.reader_drawer.ic_element
                if not getattr(ic_elem, 'name', None):
                    ic_elem.name = 'IC'
                # 保留 IC 在图上的显示（如果你也想隐藏 IC，把下面两行注释或用 clear_display_fields(ic_elem)）
                try:
                    if hasattr(ic_elem, 'label') and callable(ic_elem.label):
                        ic_elem.label(ic_elem.name)
                    elif hasattr(ic_elem, 'labeltext'):
                        ic_elem.labeltext = ic_elem.name
                except Exception:
                    pass
                d += ic_elem
                inserted.append((ic_elem.name, ic_elem, 'IC'))

            # 添加调整后的组件到绘图
            for comp_id, comp_info in adjusted_elements.items():
                elem = comp_info['element']
                comp_type = comp_info.get('type', 'unknown')

                # label 优先 element.name
                label = getattr(elem, 'name', None) or comp_id
                if not getattr(elem, 'name', None):
                    elem.name = label
                else:
                    # 对 IC 保持显示（如需隐藏 IC 也可改为 clear_display_fields(elem)）
                    try:
                        if hasattr(elem, 'label') and callable(elem.label):
                            elem.label(elem.name)
                        elif hasattr(elem, 'labeltext'):
                            elem.labeltext = elem.name
                    except Exception:
                        pass
                print(f"After cleaning, elem.label: {elem.label}")            
                d += elem
                inserted.append((label, elem, comp_type))
                print(f"已添加调整后的组件 {comp_id} (type={comp_type}) 到位置 {comp_info.get('position','?')}")

            # 添加引脚点（Dot）但不记录到 inserted（我们会跳过 Dot）
            if getattr(self.reader_drawer, 'ic_element', None):
                for pin_num, pin_name in getattr(self.reader_drawer, 'pins', {}).items():
                    try:
                        anchor = getattr(self.reader_drawer.ic_element, pin_name)
                        d += elm.Dot().at(anchor)
                    except Exception:
                        pass

        # 确保文件存在
        if not os.path.exists(output_file):
            raise RuntimeError(f"绘图文件未生成：{output_file}")

        # 读取图像，找到 content bbox
        img = Image.open(output_file).convert("RGB")
        img_w, img_h = img.size
        content_left, content_top, content_right, content_bottom = self._find_content_bbox(img)
        content_w = content_right - content_left
        content_h = content_bottom - content_top
        if content_w <= 0 or content_h <= 0:
            content_left, content_top, content_right, content_bottom = 0, 0, img_w, img_h
            content_w, content_h = img_w, img_h

        # 估计 drawing 全局 bbox（units）——基于 inserted 中的元素 get_bbox(transform=True)
        xmin_g = float('inf'); ymin_g = float('inf'); xmax_g = -float('inf'); ymax_g = -float('inf')
        for _, elem, _ in inserted:
            try:
                exmin, eymin, exmax, eymax = elem.get_bbox(transform=True)
                xmin_g = min(xmin_g, exmin)
                ymin_g = min(ymin_g, eymin)
                xmax_g = max(xmax_g, exmax)
                ymax_g = max(ymax_g, eymax)
            except Exception:
                pass

        if xmax_g == -float('inf'):
            xmin_g, ymin_g, xmax_g, ymax_g = 0.0, 0.0, 1.0, 1.0

        xmin_g -= 0.1; ymin_g -= 0.1; xmax_g += 0.1; ymax_g += 0.1
        width_units = xmax_g - xmin_g
        height_units = ymax_g - ymin_g
        if width_units <= 0 or height_units <= 0:
            width_units, height_units = 1.0, 1.0

        # units -> pixels 映射参数
        scale_x = content_w / width_units
        scale_y = content_h / height_units
        offset_x = content_left
        offset_y = content_top

        components = {}
        # 也准备一个简洁的 label->pixel bbox 映射
        bboxes_pixel_simple = {}

        for label, elem, comp_type in inserted:
            clsname = elem.__class__.__name__.lower()
            if 'dot' in clsname:
                continue

            try:
                exmin, eymin, exmax, eymax = elem.get_bbox(transform=True)
            except Exception as e:
                components[label] = {'error': f'get_bbox_failed: {e}', 'type': comp_type}
                continue

            # relative units (以 drawing 左上角为 (0,0)，Y 向下为正)
            rel_xmin = exmin - xmin_g
            rel_xmax = exmax - xmin_g
            rel_ymin = ymax_g - exmax if False else ymax_g - eymax  # just clarity; use eymax
            rel_ymin = ymax_g - eymax
            rel_ymax = ymax_g - eymin

            center_x = (exmin + exmax) / 2.0
            center_y = (eymin + eymax) / 2.0
            rel_center_x = center_x - xmin_g
            rel_center_y = ymax_g - center_y

            # units -> pixels (image left-top origin)
            left_px  = rel_xmin * scale_x + offset_x
            top_px   = rel_ymin * scale_y + offset_y
            right_px = rel_xmax * scale_x + offset_x
            bottom_px= rel_ymax * scale_y + offset_y

            left_px_i   = int(max(0, round(left_px)))
            top_px_i    = int(max(0, round(top_px)))
            right_px_i  = int(min(img_w - 1, round(right_px)))
            bottom_px_i = int(min(img_h - 1, round(bottom_px)))

            components[label] = {
                'label': label,
                'type': comp_type,
                'class': elem.__class__.__name__,
                'global_bbox_units': (exmin, eymin, exmax, eymax),
                'relative_bbox_units_from_drawing_topleft': (rel_xmin, rel_ymin, rel_xmax, rel_ymax),
                'relative_center_units_from_drawing_topleft': (rel_center_x, rel_center_y),
                'bbox_pixels_from_image_topleft': (left_px_i, top_px_i, right_px_i, bottom_px_i)
            }

            bboxes_pixel_simple[label] = (left_px_i, top_px_i, right_px_i, bottom_px_i)

        # 在图片上画 bbox
        vis = img.copy()
        draw = ImageDraw.Draw(vis)
        line_w = max(1, int(min(img_w, img_h) * 0.004))
        for info in components.values():
            if 'bbox_pixels_from_image_topleft' not in info:
                continue
            l,t,r,b = info['bbox_pixels_from_image_topleft']
            for w in range(line_w):
                draw.rectangle([l-w, t-w, r+w, b+w], outline=(255,0,0))
        out_bbox_img = os.path.splitext(output_file)[0] + "_bbox.png"
        vis.save(out_bbox_img)

        # 写 JSON
        out_data = {
            'image': {
                'file': output_file,
                'bbox_image': out_bbox_img,
                'width_px': img_w,
                'height_px': img_h,
                'content_bbox_px': (content_left, content_top, content_right, content_bottom)
            },
            'drawing_bbox_units': (xmin_g, ymin_g, xmax_g, ymax_g),
            'scale': {'scale_x_px_per_unit': scale_x, 'scale_y_px_per_unit': scale_y, 'offset_px': (offset_x, offset_y)},
            'components': components
        }
        with open(json_out, 'w', encoding='utf-8') as jf:
            json.dump(out_data, jf, ensure_ascii=False, indent=2)

        print(f"已保存：图像 {output_file}，带 bbox 图片 {out_bbox_img}，完整 JSON {json_out}")
        return output_file, out_bbox_img, json_out
        

    def print_collision_info(self):
        """打印碰撞检测和调整信息"""
        print("\n=== 碰撞检测结果 ===")
        print(f"芯片 {self.chip_info['model']}:")
        print(f"  位置: {self.chip_info['position']}")
        print(f"  Bounding Box: {self.chip_info['bbox']}")

        print(f"\n调整后的组件布局 ({len(self.adjusted_positions)} 个组件):")
        for comp_id, info in self.adjusted_positions.items():
            print(f"  {comp_id} ({info['type']}):")
            print(f"    调整后位置: {info['position']}")
            print(f"    尺寸: {info['width']:.1f} x {info['height']:.1f}")
            print(f"    连接引脚: {info['connected_pins']}")

    def get_final_layout_info(self):
        """获取最终的布局信息，供第三部分脚本使用"""
        return {
            'chip_info': self.chip_info,
            'component_positions': self.adjusted_positions,
            'chip_element': self.reader_drawer.ic_element
        }


# 测试代码
if __name__ == "__main__":
    import os

    # 智能查找JSON文件
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_file_paths = [
        'example1_netlist.json',  # 当前目录
        '../example1_netlist.json',  # 上级目录
        os.path.join(script_dir, 'example1_netlist.json'),  # 脚本所在目录
        os.path.join(script_dir, '..', 'example1_netlist.json'),  # 脚本上级目录
    ]

    json_file = None
    for path in json_file_paths:
        if os.path.exists(path):
            json_file = path
            print(f"找到JSON文件: {os.path.abspath(path)}")
            break

    if json_file is None:
        print("错误: 找不到 example1_netlist.json 文件")
        exit(1)

    # 使用第一部分的脚本
    reader_drawer = JsonReaderAndDrawer(json_file)
    reader_drawer.create_chip_element()
    reader_drawer.create_component_elements()

    # 使用第二部分的碰撞检测
    collision_detector = CollisionDetector(reader_drawer)
    collision_detector.detect_and_resolve_collisions()
    collision_detector.print_collision_info()
    collision_detector.draw_collision_free_circuit(
        'data/collision_free_circuit.png')

    print("\n=== 第二部分完成 ===")
    print("碰撞检测和位置调整完成，避免碰撞的电路图已保存")
