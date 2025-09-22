"""
第三部分：位置记录器
记录器件的最终位置和大小，生成新的JSON文件
保存布局信息供后续使用
"""
import math
import json
import os
from datetime import datetime
from typing import Dict, List, Tuple, Any
from json_reader_and_drawer import JsonReaderAndDrawer
from collision_detector import CollisionDetector


class PositionRecorder:
    def __init__(self, collision_detector: CollisionDetector):
        """初始化位置记录器"""
        self.collision_detector = collision_detector
        self.reader_drawer = collision_detector.reader_drawer
        self.layout_info = collision_detector.get_final_layout_info()

        # 获取原始JSON数据用于保留其他信息
        self.original_data = self.reader_drawer.data

    def generate_layout_json(self):
        """生成包含布局信息的新JSON"""
        print("生成布局信息JSON...")

        layout_data = {
            "metadata": {
                "generated_by": "CircuitDraw自动布局系统",
                "generation_time": datetime.now().isoformat(),
                "version": "1.0",
                "description": "自动生成的电路布局信息，包含器件位置和尺寸"
            },
            "chip": self._create_chip_layout_info(),
            "components": self._create_components_layout_info(),
            "layout_statistics": self._calculate_layout_statistics(),
            "original_netlist": {
                "nets": self.original_data.get('nets', []),
                "pin_definitions": self.original_data.get('chip', {}).get('pin_definitions', [])
            }
        }

        return layout_data

    def _create_chip_layout_info(self):
        """创建芯片布局信息"""
        chip_info = self.layout_info['chip_info']
        original_chip = self.original_data['chip']

        chip_layout = {
            "model": original_chip['model'],
            "package": original_chip.get('package', 'DIP'),
            "pin_count": original_chip['pin_count'],
            "position": {
                "x": chip_info['position'][0],
                "y": chip_info['position'][1]
            },
            "layout_size": {
                "width": chip_info['bbox']['width'],
                "height": chip_info['bbox']['height']
            },
            "bounding_box": {
                "x_min": chip_info['bbox']['x_min'],
                "x_max": chip_info['bbox']['x_max'],
                "y_min": chip_info['bbox']['y_min'],
                "y_max": chip_info['bbox']['y_max']
            },
            "schemdraw_params": original_chip.get('schemdraw_params', {}),
            "pin_definitions": original_chip.get('pin_definitions', [])
        }

        return chip_layout

    def _create_components_layout_info(self):
        """创建组件布局信息"""
        components_layout = []

        for comp_id, position_info in self.layout_info['component_positions'].items():
            original_component = self.original_data['components']
            original_comp = next(
                (c for c in original_component if c['id'] == comp_id), {})

            component_layout = {
                "id": comp_id,
                "type": position_info['type'],
                "label": position_info['label'],
                "value": original_comp.get('value', ''),
                "position": {
                    "x": position_info['position'][0],
                    "y": position_info['position'][1]
                },
                "layout_size": {
                    "width": position_info['width'],
                    "height": position_info['height']
                },
                "bounding_box": {
                    "x_min": position_info['bbox']['x_min'],
                    "x_max": position_info['bbox']['x_max'],
                    "y_min": position_info['bbox']['y_min'],
                    "y_max": position_info['bbox']['y_max']
                },
                "connected_pins": position_info['connected_pins'],
                "schemdraw_params": original_comp.get('schemdraw_params', {}),
                "placement_info": {
                    "optimal_position_achieved": self._check_if_optimal_position(
                        comp_id, position_info),
                    "distance_from_optimal": self._calculate_distance_from_optimal(
                        comp_id, position_info)
                }
            }

            components_layout.append(component_layout)

        return components_layout

    def _check_if_optimal_position(self, comp_id: str, position_info: Dict) -> bool:
        """检查是否达到了最优位置"""
        # 计算理想位置
        optimal_pos = self.collision_detector._calculate_optimal_position(
            comp_id)
        actual_pos = position_info['position']

        # 如果实际位置与理想位置的距离小于0.5，认为达到了最优位置
        distance = math.sqrt((optimal_pos[0] - actual_pos[0])**2 +
                             (optimal_pos[1] - actual_pos[1])**2)
        return distance < 0.5

    def _calculate_distance_from_optimal(self, comp_id: str, position_info: Dict) -> float:
        """计算与最优位置的距离"""
        optimal_pos = self.collision_detector._calculate_optimal_position(
            comp_id)
        actual_pos = position_info['position']

        distance = math.sqrt((optimal_pos[0] - actual_pos[0])**2 +
                             (optimal_pos[1] - actual_pos[1])**2)
        return round(distance, 2)

    def _calculate_layout_statistics(self):
        """计算布局统计信息"""
        component_positions = self.layout_info['component_positions']
        chip_bbox = self.layout_info['chip_info']['bbox']

        # 计算整体布局边界
        all_x_coords = [pos['bbox']['x_min'] for pos in component_positions.values()] + \
                       [pos['bbox']['x_max'] for pos in component_positions.values()] + \
                       [chip_bbox['x_min'], chip_bbox['x_max']]
        all_y_coords = [pos['bbox']['y_min'] for pos in component_positions.values()] + \
                       [pos['bbox']['y_max'] for pos in component_positions.values()] + \
                       [chip_bbox['y_min'], chip_bbox['y_max']]

        overall_bbox = {
            'x_min': min(all_x_coords),
            'x_max': max(all_x_coords),
            'y_min': min(all_y_coords),
            'y_max': max(all_y_coords)
        }

        # 计算布局密度
        total_component_area = sum(pos['width'] * pos['height']
                                   for pos in component_positions.values())
        total_layout_area = (overall_bbox['x_max'] - overall_bbox['x_min']) * \
            (overall_bbox['y_max'] - overall_bbox['y_min'])
        layout_density = (total_component_area / total_layout_area) * \
            100 if total_layout_area > 0 else 0

        # 计算最优位置达成率
        optimal_count = sum(1 for comp_id, pos_info in component_positions.items()
                            if self._check_if_optimal_position(comp_id, pos_info))
        optimal_rate = (optimal_count / len(component_positions)
                        ) * 100 if component_positions else 0

        statistics = {
            "total_components": len(component_positions),
            "layout_area": {
                "width": round(overall_bbox['x_max'] - overall_bbox['x_min'], 2),
                "height": round(overall_bbox['y_max'] - overall_bbox['y_min'], 2),
                "total_area": round(total_layout_area, 2)
            },
            "overall_bounding_box": overall_bbox,
            "layout_density_percentage": round(layout_density, 2),
            "optimal_position_rate_percentage": round(optimal_rate, 2),
            "component_distribution": self._analyze_component_distribution()
        }

        return statistics

    def _analyze_component_distribution(self):
        """分析组件分布情况"""
        component_positions = self.layout_info['component_positions']
        chip_center = self.layout_info['chip_info']['position']

        distribution = {
            'by_side': {'left': 0, 'right': 0, 'top': 0, 'bottom': 0},
            'by_distance': {'near': 0, 'medium': 0, 'far': 0},
            'by_type': {}
        }

        for comp_id, pos_info in component_positions.items():
            comp_pos = pos_info['position']
            comp_type = pos_info['type']

            # 按侧面分类
            if comp_pos[0] < chip_center[0]:
                distribution['by_side']['left'] += 1
            else:
                distribution['by_side']['right'] += 1

            if comp_pos[1] > chip_center[1]:
                distribution['by_side']['top'] += 1
            else:
                distribution['by_side']['bottom'] += 1

            # 按距离分类
            distance = math.sqrt((comp_pos[0] - chip_center[0])**2 +
                                 (comp_pos[1] - chip_center[1])**2)
            if distance < 3:
                distribution['by_distance']['near'] += 1
            elif distance < 6:
                distribution['by_distance']['medium'] += 1
            else:
                distribution['by_distance']['far'] += 1

            # 按类型分类
            if comp_type not in distribution['by_type']:
                distribution['by_type'][comp_type] = 0
            distribution['by_type'][comp_type] += 1

        return distribution

    def get_final_layout_info(self):
        """获取最终的布局信息，供其他脚本使用"""
        return {
            'chip_info': self.layout_info['chip_info'],
            'component_positions': self.layout_info['component_positions'],
            'chip_element': self.collision_detector.reader_drawer.ic_element
        }

    def save_layout_json(self, output_file='component_layout.json'):
        """保存布局JSON到文件"""
        layout_data = self.generate_layout_json()

        # 确保输出文件路径在data文件夹中（只有在路径不包含data时才添加）
        if not ('data' in output_file or os.path.sep in output_file):
            output_file = f'data/{output_file}'

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(layout_data, f, ensure_ascii=False, indent=2)

        print(f"布局JSON已保存到 {output_file}")
        return output_file

    def save_component_coordinates(self, output_file='component_coordinates.json'):
        """保存简化的组件坐标信息"""
        coordinates_data = {
            "metadata": {
                "description": "组件坐标信息",
                "generation_time": datetime.now().isoformat()
            },
            "chip": {
                "model": self.layout_info['chip_info']['model'],
                "position": self.layout_info['chip_info']['position']
            },
            "components": {}
        }

        for comp_id, pos_info in self.layout_info['component_positions'].items():
            coordinates_data["components"][comp_id] = {
                "type": pos_info['type'],
                "position": pos_info['position'],
                "size": [pos_info['width'], pos_info['height']]
            }

        # 确保输出文件路径在data文件夹中（只有在路径不包含data时才添加）
        if not ('data' in output_file or os.path.sep in output_file):
            output_file = f'data/{output_file}'

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(coordinates_data, f, ensure_ascii=False, indent=2)

        print(f"组件坐标已保存到 {output_file}")
        return output_file

    def generate_summary_report(self, output_file='layout_summary.txt'):
        """生成布局摘要报告"""
        layout_data = self.generate_layout_json()

        # 确保输出文件路径在data文件夹中（只有在路径不包含data时才添加）
        if not ('data' in output_file or os.path.sep in output_file):
            output_file = f'data/{output_file}'

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("电路布局摘要报告\n")
            f.write("=" * 50 + "\n\n")

            # 基本信息
            f.write(f"生成时间: {layout_data['metadata']['generation_time']}\n")
            f.write(f"芯片型号: {layout_data['chip']['model']}\n")
            f.write(
                f"组件数量: {layout_data['layout_statistics']['total_components']}\n\n")

            # 布局统计
            stats = layout_data['layout_statistics']
            f.write("布局统计:\n")
            f.write(
                f"  布局区域: {stats['layout_area']['width']:.1f} x "
                f"{stats['layout_area']['height']:.1f}\n")
            f.write(f"  布局密度: {stats['layout_density_percentage']:.1f}%\n")
            f.write(
                f"  最优位置达成率: {stats['optimal_position_rate_percentage']:.1f}%\n\n")

            # 组件分布
            dist = stats['component_distribution']
            f.write("组件分布:\n")
            f.write(
                f"  按侧面: 左{dist['by_side']['left']} 右{dist['by_side']['right']} ")
            f.write(
                f"上{dist['by_side']['top']} 下{dist['by_side']['bottom']}\n")
            f.write(
                f"  按距离: 近{dist['by_distance']['near']} 中{dist['by_distance']['medium']} ")
            f.write(f"远{dist['by_distance']['far']}\n")
            f.write(f"  按类型: {dict(dist['by_type'])}\n\n")

            # 组件详细信息
            f.write("组件详细位置:\n")
            for comp in layout_data['components']:
                f.write(f"  {comp['id']} ({comp['type']}): ")
                f.write(
                    f"({comp['position']['x']:.2f}, {comp['position']['y']:.2f}) ")
                f.write(
                    f"尺寸 {comp['layout_size']['width']:.1f}x{comp['layout_size']['height']:.1f}")
                if not comp['placement_info']['optimal_position_achieved']:
                    f.write(
                        f" [偏离最优 {comp['placement_info']['distance_from_optimal']:.2f}]")
                f.write("\n")

        print(f"布局摘要报告已保存到 {output_file}")
        return output_file

    def print_layout_summary(self):
        """打印布局摘要"""
        layout_data = self.generate_layout_json()

        print("\n=== 布局摘要 ===")
        print(f"芯片: {layout_data['chip']['model']}")
        print(f"组件数量: {layout_data['layout_statistics']['total_components']}")

        stats = layout_data['layout_statistics']
        print(
            f"布局区域: {stats['layout_area']['width']:.1f} x {stats['layout_area']['height']:.1f}")
        print(f"布局密度: {stats['layout_density_percentage']:.1f}%")
        print(f"最优位置达成率: {stats['optimal_position_rate_percentage']:.1f}%")

        print("\n组件最终位置:")
        for comp in layout_data['components']:
            status = "✓" if comp['placement_info']['optimal_position_achieved'] else "⚠"
            print(f"  {status} {comp['id']} ({comp['type']}): "
                  f"({comp['position']['x']:.2f}, {comp['position']['y']:.2f})")

    def _get_component_class_mapping(self):
        """获取组件类型到YOLO类别ID的映射"""
        component_types = set()
        for pos_info in self.layout_info['component_positions'].values():
            component_types.add(pos_info['type'])

        # 添加芯片类型
        component_types.add('chip')

        # 按字母顺序排序，确保一致性
        sorted_types = sorted(component_types)

        # 创建类型到ID的映射
        class_mapping = {comp_type: idx for idx,
                         comp_type in enumerate(sorted_types)}

        return class_mapping, sorted_types

    def _calculate_canvas_size(self):
        """计算画布的实际尺寸"""
        layout_data = self.generate_layout_json()
        stats = layout_data['layout_statistics']

        # 获取整体边界框
        overall_bbox = stats['overall_bounding_box']

        # 添加一些边距，确保所有组件都在画布范围内
        margin = 2.0
        canvas_width = overall_bbox['x_max'] - \
            overall_bbox['x_min'] + 2 * margin
        canvas_height = overall_bbox['y_max'] - \
            overall_bbox['y_min'] + 2 * margin

        # 画布的原点（左上角）
        canvas_origin_x = overall_bbox['x_min'] - margin
        canvas_origin_y = overall_bbox['y_max'] + margin  # YOLO坐标系Y轴向下

        return canvas_width, canvas_height, canvas_origin_x, canvas_origin_y

    def _convert_to_yolo_format(
            self, x, y, width, height, canvas_width, canvas_height,
            canvas_origin_x, canvas_origin_y):
        """将绝对坐标转换为YOLO格式的归一化坐标"""
        # 转换为画布坐标系（左上角为原点，Y轴向下）
        canvas_x = x - canvas_origin_x
        canvas_y = canvas_origin_y - y  # 翻转Y轴

        # 计算边界框中心的归一化坐标
        x_center_norm = canvas_x / canvas_width
        y_center_norm = canvas_y / canvas_height

        # 计算归一化的宽度和高度
        width_norm = width / canvas_width
        height_norm = height / canvas_height

        # 确保坐标在0-1范围内
        x_center_norm = max(0, min(1, x_center_norm))
        y_center_norm = max(0, min(1, y_center_norm))
        width_norm = max(0, min(1, width_norm))
        height_norm = max(0, min(1, height_norm))

        return x_center_norm, y_center_norm, width_norm, height_norm

    def save_yolo_annotations(
            self, output_file='yolo_annotations.txt',
            class_mapping_file='yolo_classes.txt'):
        """保存YOLO格式的标注文件"""
        print("生成YOLO格式标注...")

        # 获取类别映射
        class_mapping, class_names = self._get_component_class_mapping()

        # 计算画布尺寸
        canvas_width, canvas_height, canvas_origin_x, canvas_origin_y = (
            self._calculate_canvas_size())

        print(f"画布尺寸: {canvas_width:.2f} x {canvas_height:.2f}")
        print(f"画布原点: ({canvas_origin_x:.2f}, {canvas_origin_y:.2f})")

        # 确保输出文件路径在data文件夹中（只有在路径不包含data时才添加）
        if not ('data' in output_file or os.path.sep in output_file):
            output_file = f'data/{output_file}'
        if not ('data' in class_mapping_file or os.path.sep in class_mapping_file):
            class_mapping_file = f'data/{class_mapping_file}'

        # 生成YOLO标注
        yolo_annotations = []

        # 添加芯片标注
        chip_info = self.layout_info['chip_info']
        chip_x, chip_y = chip_info['position']
        chip_width = chip_info['bbox']['width']
        chip_height = chip_info['bbox']['height']

        chip_x_norm, chip_y_norm, chip_w_norm, chip_h_norm = self._convert_to_yolo_format(
            chip_x, chip_y, chip_width, chip_height,
            canvas_width, canvas_height, canvas_origin_x, canvas_origin_y
        )

        chip_class_id = class_mapping['chip']
        yolo_annotations.append(
            f"{chip_class_id} {chip_x_norm:.6f} {chip_y_norm:.6f} "
            f"{chip_w_norm:.6f} {chip_h_norm:.6f}")

        # 添加组件标注（按照组件ID排序）
        sorted_components = sorted(self.layout_info['component_positions'].items(),
                                   key=lambda x: int(x[0]) if x[0].isdigit() else float('inf'))

        for comp_id, pos_info in sorted_components:
            comp_type = pos_info['type']
            comp_x, comp_y = pos_info['position']
            comp_width = pos_info['width']
            comp_height = pos_info['height']

            # 转换为YOLO格式
            x_norm, y_norm, w_norm, h_norm = self._convert_to_yolo_format(
                comp_x, comp_y, comp_width, comp_height,
                canvas_width, canvas_height, canvas_origin_x, canvas_origin_y
            )

            class_id = class_mapping[comp_type]
            # 添加注释信息，便于调试和验证
            yolo_annotations.append(
                f"{class_id} {x_norm:.6f} {y_norm:.6f} {w_norm:.6f} {h_norm:.6f}  "
                f"# {comp_id}_{comp_type}")

            print(f"  {comp_id} ({comp_type}): class_id={class_id}, "
                  f"norm_coords=({x_norm:.3f}, {y_norm:.3f}, {w_norm:.3f}, {h_norm:.3f})")

        # 保存YOLO标注文件
        with open(output_file, 'w', encoding='utf-8') as f:
            for annotation in yolo_annotations:
                f.write(annotation + '\n')

        # 保存类别映射文件
        with open(class_mapping_file, 'w', encoding='utf-8') as f:
            for class_name in class_names:
                f.write(class_name + '\n')

        print(f"YOLO标注已保存到 {output_file}")
        print(f"类别映射已保存到 {class_mapping_file}")

        # 返回详细信息
        return {
            'annotation_file': output_file,
            'class_mapping_file': class_mapping_file,
            'canvas_size': (canvas_width, canvas_height),
            'canvas_origin': (canvas_origin_x, canvas_origin_y),
            'class_mapping': class_mapping,
            'total_objects': len(yolo_annotations)
        }

    def save_yolo_dataset_info(self, output_file='yolo_dataset_info.json'):
        """保存YOLO数据集的详细信息"""
        class_mapping, class_names = self._get_component_class_mapping()
        canvas_width, canvas_height, canvas_origin_x, canvas_origin_y = (
            self._calculate_canvas_size())

        dataset_info = {
            "metadata": {
                "format": "YOLO",
                "description": "电路图组件检测数据集标注信息",
                "generation_time": datetime.now().isoformat(),
                "coordinate_system": "归一化坐标，左上角为原点，Y轴向下"
            },
            "canvas_info": {
                "width": canvas_width,
                "height": canvas_height,
                "origin_x": canvas_origin_x,
                "origin_y": canvas_origin_y,
                "description": "画布实际尺寸和原点位置"
            },
            "class_mapping": {
                "total_classes": len(class_names),
                "classes": [{"id": idx, "name": name} for idx, name in enumerate(class_names)],
                "mapping": class_mapping
            },
            "annotation_format": {
                "description": "每行格式: <class_id> <x_center> <y_center> <width> <height>",
                "coordinate_range": "所有坐标值在0-1之间",
                "center_based": True
            },
            "statistics": self._get_yolo_statistics()
        }

        # 确保输出文件路径在data文件夹中（只有在路径不包含data时才添加）
        if not ('data' in output_file or os.path.sep in output_file):
            output_file = f'data/{output_file}'

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(dataset_info, f, ensure_ascii=False, indent=2)

        print(f"YOLO数据集信息已保存到 {output_file}")
        return output_file

    def _get_yolo_statistics(self):
        """获取YOLO数据集的统计信息"""
        class_mapping, _ = self._get_component_class_mapping()

        # 统计每个类别的数量
        class_counts = {class_name: 0 for class_name in class_mapping.keys()}

        # 芯片计数
        class_counts['chip'] = 1

        # 组件计数
        for pos_info in self.layout_info['component_positions'].values():
            comp_type = pos_info['type']
            class_counts[comp_type] += 1

        # 计算边界框大小分布
        bbox_sizes = []
        canvas_width, canvas_height, _, _ = self._calculate_canvas_size()

        # 芯片尺寸
        chip_info = self.layout_info['chip_info']
        chip_w_norm = chip_info['bbox']['width'] / canvas_width
        chip_h_norm = chip_info['bbox']['height'] / canvas_height
        bbox_sizes.append(
            {'type': 'chip', 'width': chip_w_norm, 'height': chip_h_norm})

        # 组件尺寸
        for comp_id, pos_info in self.layout_info['component_positions'].items():
            w_norm = pos_info['width'] / canvas_width
            h_norm = pos_info['height'] / canvas_height
            bbox_sizes.append({
                'type': pos_info['type'],
                'width': w_norm,
                'height': h_norm
            })

        return {
            "total_objects": sum(class_counts.values()),
            "class_distribution": class_counts,
            "bbox_size_range": {
                "min_width": min(bbox['width'] for bbox in bbox_sizes),
                "max_width": max(bbox['width'] for bbox in bbox_sizes),
                "min_height": min(bbox['height'] for bbox in bbox_sizes),
                "max_height": max(bbox['height'] for bbox in bbox_sizes),
                "avg_width": sum(bbox['width'] for bbox in bbox_sizes) / len(bbox_sizes),
                "avg_height": sum(bbox['height'] for bbox in bbox_sizes) / len(bbox_sizes)
            }
        }


# 添加必要的 import

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

    # 使用前两个部分的脚本
    reader_drawer = JsonReaderAndDrawer(json_file)
    reader_drawer.create_chip_element()
    reader_drawer.create_component_elements()

    collision_detector = CollisionDetector(reader_drawer)
    collision_detector.detect_and_resolve_collisions()

    # 使用第三部分的位置记录器
    position_recorder = PositionRecorder(collision_detector)
    position_recorder.print_layout_summary()

    # 保存各种格式的输出文件
    position_recorder.save_layout_json('complete_layout.json')
    position_recorder.save_component_coordinates('component_coordinates.json')
    position_recorder.generate_summary_report('layout_summary.txt')

    # 生成YOLO格式标注
    yolo_result = position_recorder.save_yolo_annotations(
        'yolo_annotations.txt', 'yolo_classes.txt')
    position_recorder.save_yolo_dataset_info('yolo_dataset_info.json')

    print(f"\nYOLO标注统计:")
    print(f"  总对象数: {yolo_result['total_objects']}")
    print(f"  类别数量: {len(yolo_result['class_mapping'])}")
    print(
        f"  画布尺寸: {yolo_result['canvas_size'][0]:.1f} x {yolo_result['canvas_size'][1]:.1f}")

    print("\n=== 第三部分完成 ===")
    print("布局信息已记录并保存到JSON文件")
    print("YOLO格式标注文件已生成")
