"""
主脚本：协调运行三个部分
1. 读取JSON文件并绘制器件
2. 应用碰撞检测算法
3. 记录位置信息并生成新的JSON文件

所有生成的文件都保存在data文件夹中
"""
import os
import sys
import json
import traceback
from datetime import datetime

# 添加当前目录到路径，以便导入其他模块
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from json_reader_and_drawer import JsonReaderAndDrawer
    from collision_detector import CollisionDetector
    from position_recorder import PositionRecorder
except ImportError as e:
    print(f"导入模块时出错: {e}")
    print("请确保所有脚本文件都在同一目录中")
    sys.exit(1)


class CircuitLayoutManager:
    """电路布局管理器，协调三个部分的运行"""

    def __init__(self, json_file: str, output_dir: str = 'data'):
        """初始化电路布局管理器"""
        self.json_file = json_file
        self.output_dir = output_dir

        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)

        print("=== CircuitDraw自动布局系统 ===")
        print(f"输入文件: {json_file}")
        print(f"输出目录: {self.output_dir}")
        print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    def run_complete_layout_process(self):
        """运行完整的布局流程"""
        try:
            reader_drawer = self._step1_create_basic_circuit()
            collision_detector = self._step2_detect_collisions(reader_drawer)
            position_recorder, yolo_result = self._step3_record_positions(
                collision_detector)

            return self._generate_final_result(
                position_recorder, yolo_result)

        except (FileNotFoundError, ValueError, ImportError) as exc:
            print(f"❌ 错误: {exc}")
            traceback.print_exc()
            return {'success': False, 'error': str(exc)}

    def _step1_create_basic_circuit(self):
        """第一部分：读取JSON并创建基础绘图"""
        print("步骤 1/3: 读取JSON文件并创建基础绘图")
        print("-" * 50)

        reader_drawer = JsonReaderAndDrawer(self.json_file)
        reader_drawer.create_chip_element()
        reader_drawer.create_component_elements()

        basic_circuit_file = os.path.join(self.output_dir, 'basic_circuit.png')
        reader_drawer.draw_basic_circuit(basic_circuit_file)

        print(f"✓ 基础电路图已保存: {basic_circuit_file}")
        component_count = len(reader_drawer.component_elements)
        print(f"✓ 第一部分完成：已创建 {component_count} 个组件元素\n")

        return reader_drawer

    def _step2_detect_collisions(self, reader_drawer):
        """第二部分：碰撞检测和位置调整"""
        print("步骤 2/3: 碰撞检测和位置调整")
        print("-" * 50)

        collision_detector = CollisionDetector(reader_drawer)
        collision_detector.detect_and_resolve_collisions()

        collision_free_circuit_file = os.path.join(
            self.output_dir, 'collision_free_circuit.png')
        collision_detector.draw_collision_free_circuit(
            collision_free_circuit_file)

        print(f"✓ 避免碰撞的电路图已保存: {collision_free_circuit_file}")
        print("✓ 第二部分完成：碰撞检测和位置调整完成\n")

        return collision_detector

    def _step3_record_positions(self, collision_detector):
        """第三部分：记录位置信息"""
        print("步骤 3/3: 记录位置信息并生成JSON文件")
        print("-" * 50)

        position_recorder = PositionRecorder(collision_detector)

        # 保存各种格式的输出文件
        layout_json_file = os.path.join(
            self.output_dir, 'complete_layout.json')
        coordinates_file = os.path.join(
            self.output_dir, 'component_coordinates.json')
        summary_file = os.path.join(self.output_dir, 'layout_summary.txt')
        yolo_annotation_file = os.path.join(
            self.output_dir, 'yolo_annotations.txt')
        yolo_classes_file = os.path.join(self.output_dir, 'yolo_classes.txt')
        yolo_info_file = os.path.join(
            self.output_dir, 'yolo_dataset_info.json')

        position_recorder.save_layout_json(layout_json_file)
        position_recorder.save_component_coordinates(coordinates_file)
        position_recorder.generate_summary_report(summary_file)

        yolo_result = position_recorder.save_yolo_annotations(
            yolo_annotation_file, yolo_classes_file)
        position_recorder.save_yolo_dataset_info(yolo_info_file)

        print(f"✓ 完整布局信息已保存: {layout_json_file}")
        print(f"✓ 组件坐标已保存: {coordinates_file}")
        print(f"✓ 布局摘要已保存: {summary_file}")
        print(f"✓ YOLO标注已保存: {yolo_annotation_file}")
        print(f"✓ YOLO类别映射已保存: {yolo_classes_file}")
        print(f"✓ YOLO数据集信息已保存: {yolo_info_file}")

        position_recorder.print_layout_summary()

        return position_recorder, yolo_result

    def _generate_final_result(self, position_recorder, yolo_result):
        """生成最终结果和输出摘要"""
        basic_circuit_file = os.path.join(self.output_dir, 'basic_circuit.png')
        collision_free_circuit_file = os.path.join(
            self.output_dir, 'collision_free_circuit.png')
        layout_json_file = os.path.join(
            self.output_dir, 'complete_layout.json')
        coordinates_file = os.path.join(
            self.output_dir, 'component_coordinates.json')
        summary_file = os.path.join(self.output_dir, 'layout_summary.txt')
        yolo_annotation_file = os.path.join(
            self.output_dir, 'yolo_annotations.txt')
        yolo_classes_file = os.path.join(self.output_dir, 'yolo_classes.txt')
        yolo_info_file = os.path.join(
            self.output_dir, 'yolo_dataset_info.json')

        print("\n" + "=" * 60)
        print("🎉 所有步骤完成！生成的文件:")
        print(f"  📊 基础电路图: {basic_circuit_file}")
        print(f"  🔧 优化电路图: {collision_free_circuit_file}")
        print(f"  📋 完整布局JSON: {layout_json_file}")
        print(f"  📍 组件坐标JSON: {coordinates_file}")
        print(f"  📝 布局摘要报告: {summary_file}")
        print(f"  🎯 YOLO标注文件: {yolo_annotation_file}")
        print(f"  🏷️ YOLO类别映射: {yolo_classes_file}")
        print(f"  📊 YOLO数据集信息: {yolo_info_file}")
        print("=" * 60)

        return {
            'success': True,
            'files_generated': {
                'basic_circuit': basic_circuit_file,
                'optimized_circuit': collision_free_circuit_file,
                'layout_json': layout_json_file,
                'coordinates_json': coordinates_file,
                'summary_report': summary_file,
                'yolo_annotations': yolo_annotation_file,
                'yolo_classes': yolo_classes_file,
                'yolo_dataset_info': yolo_info_file
            },
            'layout_info': position_recorder.get_final_layout_info(),
            'yolo_info': yolo_result
        }

    def validate_inputs(self):
        """验证输入文件"""
        if not os.path.exists(self.json_file):
            raise FileNotFoundError(f"找不到JSON文件: {self.json_file}")

        # 验证JSON文件格式
        try:
            with open(self.json_file, 'r', encoding='utf-8') as json_file:
                data = json.load(json_file)

            # 检查必要的字段
            required_fields = ['chip', 'components', 'nets']
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"JSON文件缺少必要字段: {field}")

            print("✓ JSON文件验证通过")
            return True

        except json.JSONDecodeError as json_error:
            raise ValueError(f"JSON文件格式错误: {json_error}") from json_error


def find_json_file():
    """智能查找JSON文件"""
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # 可能的JSON文件路径
    json_file_paths = [
        'example1_netlist.json',  # 当前目录
        '../example1_netlist.json',  # 上级目录
        os.path.join(script_dir, 'example1_netlist.json'),  # 脚本所在目录
        os.path.join(script_dir, '..', 'example1_netlist.json'),  # 脚本上级目录
        os.path.join(os.path.dirname(script_dir),
                     'example1_netlist.json'),  # 工作区根目录
        # 也尝试example2
        'example2_netlist.json',
        '../example2_netlist.json',
        os.path.join(script_dir, 'example2_netlist.json'),
        os.path.join(script_dir, '..', 'example2_netlist.json'),
    ]

    for path in json_file_paths:
        if os.path.exists(path):
            abs_path = os.path.abspath(path)
            print(f"🔍 找到JSON文件: {abs_path}")
            return abs_path

    # 如果没找到，列出可能的位置
    print("❌ 找不到JSON文件，已搜索的路径:")
    for path in json_file_paths:
        print(f"   - {os.path.abspath(path)}")

    return None


def main():
    """主函数"""
    print("CircuitDraw 自动电路布局系统")
    print("=" * 60)

    # 查找JSON文件
    json_file = find_json_file()
    if json_file is None:
        print("\n请确保JSON文件存在于以下位置之一:")
        print("  - 当前目录: example1_netlist.json 或 example2_netlist.json")
        print("  - 上级目录: ../example1_netlist.json 或 ../example2_netlist.json")
        sys.exit(1)

    # 创建布局管理器并运行
    try:
        layout_manager = CircuitLayoutManager(json_file)
        layout_manager.validate_inputs()
        result = layout_manager.run_complete_layout_process()

        if result['success']:
            print("\n✅ 布局生成成功！")
            print(f"📁 所有文件已保存在 {layout_manager.output_dir} 文件夹中")
        else:
            print(f"\n❌ 布局生成失败: {result['error']}")
            sys.exit(1)

    except (FileNotFoundError, ValueError, ImportError) as exc:
        print(f"\n❌ 发生错误: {exc}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
