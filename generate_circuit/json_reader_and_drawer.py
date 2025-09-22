"""
第一部分：JSON文件读取器和SchemDraw绘制器
读取JSON文件，解析器件信息，使用SchemDraw绘制器件
支持在JSON文件中设置器件的长度、大小和旋转角度
"""
import json
import math
from schemdraw import Drawing
import schemdraw.elements as elm
from typing import Dict, List, Tuple, Any


class JsonReaderAndDrawer:
    def __init__(self, json_file: str):
        """初始化JSON读取器和绘制器"""
        with open(json_file, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

        self.chip = self.data['chip']
        self.components = {c['id']: c for c in self.data['components']}
        self.nets = {n['net_id']: n['connections'] for n in self.data['nets']}
        self.pins = {p['number']: p['name']
                     for p in self.chip['pin_definitions']}

        # 绘制信息存储
        self.drawing = None
        self.ic_element = None
        self.component_elements = {}  # component_id -> schemdraw element

        # 分析连接关系
        self._analyze_connections()

    def _analyze_connections(self):
        """分析组件与芯片引脚的连接关系"""
        self.pin_to_components = {}  # pin_number -> [component_ids]
        self.component_to_pins = {}  # component_id -> [pin_numbers]

        for net_id, connections in self.nets.items():
            chip_pins = []
            components = []

            for conn in connections:
                if conn['type'] == 'chip_pin':
                    chip_pins.append(conn['pin_number'])
                elif conn['type'] == 'component_port':
                    comp_id = conn.get('component_id') or conn.get('component')
                    if comp_id:
                        components.append(comp_id)

            # 建立连接关系
            for pin in chip_pins:
                if pin not in self.pin_to_components:
                    self.pin_to_components[pin] = []
                self.pin_to_components[pin].extend(components)

            for comp_id in components:
                if comp_id not in self.component_to_pins:
                    self.component_to_pins[comp_id] = []
                self.component_to_pins[comp_id].extend(chip_pins)

    def _get_schemdraw_element_class(self, component_type: str):
        """获取对应的schemdraw元素类"""
        type_mapping = {
            'resistor': elm.Resistor,
            'capacitor': elm.Capacitor,
            'LED': elm.LED,
            'ground': elm.Ground,
            'voltage_source': elm.SourceV
        }
        return type_mapping.get(component_type, elm.Resistor)

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

    def _calculate_initial_component_position(self, component_id: str) -> Tuple[float, float]:
        """根据连接关系计算组件的初始位置"""
        if component_id not in self.component_to_pins:
            return (2.0, 2.0)  # 默认位置

        # 获取连接的引脚
        connected_pins = self.component_to_pins[component_id]
        if not connected_pins:
            return (2.0, 2.0)

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

    def create_chip_element(self):
        """创建芯片元素"""
        print(f"创建芯片 {self.chip['model']} 元素...")

        # 创建IC元素，应用schemdraw参数
        self.ic_element = elm.Ic()

        # 获取芯片的schemdraw参数
        chip_params = self.chip.get('schemdraw_params', {})
        spacing = chip_params.get('spacing', 1.5)
        pad = chip_params.get('pad', 1.5)
        leadlen = chip_params.get('leadlen', 0.3)

        self.ic_element.side('L', spacing=spacing, pad=pad, leadlen=leadlen)
        self.ic_element.side('R', spacing=spacing * 1.3, leadlen=leadlen)
        self.ic_element.side(
            'T', pad=pad, spacing=spacing * 0.7, leadlen=leadlen)
        self.ic_element.side('B', spacing=spacing * 0.7, leadlen=leadlen)

        print(
            f"    应用芯片schemdraw参数: spacing={spacing}, pad={pad}, leadlen={leadlen}")

        # 配置引脚
        pin_configs = [
            (1, 'B'), (2, 'L'), (3, 'R'), (4, 'T'), (5, 'R'),
            (6, 'L'), (7, 'L'), (8, 'T'), (9, 'R')
        ]

        for pin_num, side in pin_configs:
            if pin_num in self.pins:
                pin_name = self.pins[pin_num]
                self.ic_element.pin(name=pin_name, side=side, pin=str(pin_num))

        self.ic_element.label(self.chip['model'])

        return self.ic_element

    def create_component_elements(self):
        """创建所有组件元素"""
        print("创建组件元素...")

        for comp_id, component in self.components.items():
            comp_type = component['type']
            # label = component.get('label', '').strip() or component.get(
            #     'value', '').strip() or comp_id

            label = component.get('label', None) or component.get('value', None)
            label = label.strip() if label else ''

            # 计算初始位置
            position = self._calculate_initial_component_position(comp_id)

            print(f"创建组件 {comp_id} ({comp_type}) 在位置 {position}")

            # 获取schemdraw元素类
            ElementClass = self._get_schemdraw_element_class(comp_type)

            # 获取schemdraw参数
            schemdraw_params = component.get('schemdraw_params', {})
            
            try:
                if comp_type == 'voltage_source':
                    element = elm.SourceV().at(position)
                    # 应用电压源参数
                    element = self._apply_schemdraw_params_safely(
                        element, schemdraw_params, [], comp_type)
                    if label.strip():
                        element = element.label(label, 'top')

                elif comp_type == 'resistor':
                    element = ElementClass().at(position)
                    # 应用电阻参数（长度、旋转等）
                    element = self._apply_schemdraw_params_safely(
                        element, schemdraw_params, ['length', 'theta'], comp_type)
                    if label.strip():
                        element = element.label(label, 'top')

                elif comp_type == 'capacitor':
                    element = ElementClass().at(position)
                    # 应用电容参数
                    element = self._apply_schemdraw_params_safely(
                        element, schemdraw_params, ['length', 'theta', 'width'], comp_type)
                    if label.strip():
                        element = element.label(label, 'bottom')

                elif comp_type == 'LED':
                    element = ElementClass().at(position)
                    # 应用LED参数
                    element = self._apply_schemdraw_params_safely(
                        element, schemdraw_params, ['length', 'theta', 'width'], comp_type)
                    if label.strip():
                        element = element.label(label, 'right')

                elif comp_type == 'ground':
                    element = elm.Ground().at(position)
                    # 地线符号通常不需要特殊参数

                else:
                    element = ElementClass().at(position)
                    # 对于其他类型，安全地应用通用参数
                    element = self._apply_schemdraw_params_safely(
                        element, schemdraw_params, [], comp_type)
                    if label.strip():
                        element = element.label(label)

                self.component_elements[comp_id] = {
                    'element': element,
                    'position': position,
                    'type': comp_type,
                    'label': label
                }

                print(f"    成功创建组件 {comp_id}")
            except Exception as e:
                print(f"    创建组件 {comp_id} 时出错: {e}")

        return self.component_elements

    def _apply_schemdraw_params_safely(
            self, element, params: Dict, allowed_params: List[str], comp_type: str):
        """安全地将schemdraw参数应用到元素上"""
        if not params:
            return element

        for param_name, param_value in params.items():
            # 跳过不在允许列表中的参数（如果有允许列表的话）
            if allowed_params and param_name not in allowed_params:
                continue

            try:
                # 检查元素是否有这个方法
                if hasattr(element, param_name):
                    method = getattr(element, param_name)
                    if callable(method):
                        element = method(param_value)
                        print(
                            f"        成功应用 {comp_type} 参数 {param_name}={param_value}")
                    else:
                        print(f"        跳过 {comp_type} 参数 {param_name} (不是方法)")
                else:
                    print(f"        跳过 {comp_type} 参数 {param_name} (元素不支持)")

            except Exception as e:
                print(
                    f"        警告: 应用 {comp_type} 参数 {param_name}={param_value} 失败: {e}")

        return element

    def draw_basic_circuit(self, output_file='basic_circuit.png'):
        """绘制基础电路图（不考虑碰撞检测）"""
        print(f"正在绘制基础电路图到 {output_file}...")

        with Drawing(file=output_file, transparent=False) as d:
            d.config(fontsize=10)
            d.config(unit=1.6)

            # 添加芯片到绘图
            if self.ic_element:
                d += self.ic_element

            # 添加组件到绘图
            for comp_id, comp_info in self.component_elements.items():
                d += comp_info['element']
                print(
                    f"已添加组件 {comp_id} ({comp_info['type']}) 到位置 {comp_info['position']}")

            # 添加引脚标记点
            for pin_num, pin_name in self.pins.items():
                if hasattr(self.ic_element, pin_name):
                    try:
                        anchor = getattr(self.ic_element, pin_name)
                        d += elm.Dot().at(anchor)
                    except AttributeError:
                        pass

        print(f"基础电路图已保存到 {output_file}")
        return output_file

    def get_component_info(self):
        """获取组件信息，用于后续的碰撞检测"""
        component_info = {}

        for comp_id, comp_data in self.component_elements.items():
            component = self.components[comp_id]
            comp_type = component['type']

            # 计算组件的基础尺寸
            width, height = self._get_component_basic_size(comp_type, comp_id)

            component_info[comp_id] = {
                'position': comp_data['position'],
                'type': comp_type,
                'label': comp_data['label'],
                'width': width,
                'height': height,
                'connected_pins': self.component_to_pins.get(comp_id, []),
                'element': comp_data['element']
            }

        return component_info

    def _get_component_basic_size(self, comp_type: str, comp_id: str = None) -> Tuple[float, float]:
        """获取组件的基础尺寸"""
        try:
            component = self.components.get(comp_id) if comp_id else None

            # 优先使用JSON中定义的布局尺寸
            if component and 'layout_size' in component:
                size_info = component['layout_size']
                width = size_info['width']
                height = size_info['height']
                print(
                    f"    从JSON layout_size获取组件 {comp_id} ({comp_type}) "
                    f"尺寸: ({width:.1f}, {height:.1f})")

            # 回退到旧格式支持 'size'
            elif component and 'size' in component:
                size_info = component['size']
                width = size_info['width']
                height = size_info['height']
                print(
                    f"    从JSON size获取组件 {comp_id} ({comp_type}) 尺寸: ({width:.1f}, {height:.1f})")

            else:
                # 使用基于schemdraw参数的估算尺寸
                if component and 'schemdraw_params' in component:
                    params = component['schemdraw_params']
                    width, height = self._calculate_size_from_schemdraw_params(
                        comp_type, params)
                    print(
                        f"    从schemdraw_params计算组件 {comp_id} ({comp_type}) "
                        f"尺寸: ({width:.1f}, {height:.1f})")
                else:
                    # 使用默认尺寸
                    if comp_type == 'resistor':
                        width, height = 3.0, 0.8
                    elif comp_type == 'capacitor':
                        width, height = 2.0, 1.5
                    elif comp_type == 'LED':
                        width, height = 1.5, 1.5
                    elif comp_type == 'ground':
                        width, height = 1.2, 1.2
                    elif comp_type == 'voltage_source':
                        width, height = 2.5, 2.5
                    else:
                        width, height = 2.0, 1.0

                    print(
                        f"    使用默认组件 {comp_id} ({comp_type}) 尺寸: ({width:.1f}, {height:.1f})")

            return (width, height)

        except Exception as e:
            print(f"    警告: 无法获取组件 {comp_type} 的尺寸: {e}")
            return (2.0, 1.0)

    def _calculate_size_from_schemdraw_params(
            self, comp_type: str, params: Dict) -> Tuple[float, float]:
        """根据schemdraw参数计算组件的布局尺寸"""
        try:
            if comp_type == 'resistor':
                length = params.get('length', 3.0)
                loops = params.get('loops', 6)
                width = length + 0.5
                height = 0.6 + (loops / 10.0)

            elif comp_type == 'capacitor':
                cap_width = params.get('width', 1.5)
                cap_length = params.get('length', 0.8)
                width = cap_width + 0.5
                height = cap_length + 1.0

            elif comp_type == 'LED':
                led_width = params.get('width', 1.0)
                led_length = params.get('length', 1.0)
                width = led_width + 0.5
                height = led_length + 0.5

            elif comp_type == 'voltage_source':
                radius = params.get('radius', 1.0)
                width = height = (radius * 2) + 0.4

            elif comp_type == 'ground':
                width = height = 1.0

            else:
                width, height = 2.0, 1.0

            return (width, height)

        except Exception as e:
            print(f"    警告: 无法从schemdraw参数计算 {comp_type} 尺寸: {e}")
            return (2.0, 1.0)

    def get_chip_info(self):
        """获取芯片信息"""
        # 计算芯片的尺寸
        if 'layout_size' in self.chip:
            chip_width = self.chip['layout_size']['width']
            chip_height = self.chip['layout_size']['height']
        elif 'size' in self.chip:
            chip_width = self.chip['size']['width']
            chip_height = self.chip['size']['height']
        else:
            # 根据引脚数量和schemdraw参数计算
            pin_count = self.chip['pin_count']
            chip_params = self.chip.get('schemdraw_params', {})
            spacing = chip_params.get('spacing', 1.5)
            pad = chip_params.get('pad', 1.5)
            leadlen = chip_params.get('leadlen', 1)

            if pin_count <= 8:
                core_width, core_height = 2.5, 2.0
            elif pin_count <= 14:
                core_width, core_height = 2.5, 3.0
            elif pin_count <= 16:
                core_width, core_height = 2.5, 3.5
            else:
                core_width = 2.5
                core_height = 2.0 + (pin_count - 8) * 0.2

            chip_width = core_width + 2 * (leadlen + pad)
            chip_height = core_height + 2 * pad

        chip_bbox = {
            'x_min': -chip_width/2, 'x_max': chip_width/2,
            'y_min': -chip_height/2, 'y_max': chip_height/2,
            'width': chip_width, 'height': chip_height
        }

        return {
            'model': self.chip['model'],
            'position': (0, 0),  # 芯片放在原点
            'bbox': chip_bbox,
            'element': self.ic_element
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

    # 使用找到的JSON文件
    reader_drawer = JsonReaderAndDrawer(json_file)

    # 创建芯片元素
    reader_drawer.create_chip_element()

    # 创建组件元素
    reader_drawer.create_component_elements()

    # 绘制基础电路图
    reader_drawer.draw_basic_circuit('data/basic_circuit.png')

    # 输出组件信息供后续脚本使用
    component_info = reader_drawer.get_component_info()
    chip_info = reader_drawer.get_chip_info()

    print("\n=== 第一部分完成 ===")
    print(f"已创建 {len(component_info)} 个组件元素")
    print("基础电路图已保存，组件信息可供碰撞检测脚本使用")
