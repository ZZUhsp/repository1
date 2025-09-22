# CircuitDraw 自动电路布局系统

这个系统将原始的电路布局脚本分为三个独立的部分，实现了模块化的电路自动布局功能。

## 文件结构

```
data/
├── json_reader_and_drawer.py    # 第一部分：JSON读取和基础绘图
├── collision_detector.py        # 第二部分：碰撞检测和位置调整
├── position_recorder.py         # 第三部分：位置记录和JSON生成
├── main.py                      # 主脚本，协调运行三个部分
└── README.md                    # 使用说明
```

## 功能说明

### 第一部分：json_reader_and_drawer.py

- **功能**：读取 JSON 文件，解析器件信息，使用 SchemDraw 绘制器件
- **特性**：
  - 支持在 JSON 文件中设置器件的长度、大小和旋转角度
  - 支持多种器件类型（电阻、电容、LED、电压源、地线等）
  - 根据连接关系计算器件的初始位置
  - 生成基础电路图

### 第二部分：collision_detector.py

- **功能**：在第一部分的基础上添加碰撞检测算法
- **特性**：
  - 检测器件之间的重叠
  - 检测器件与芯片的重叠
  - 使用螺旋式搜索算法调整器件位置
  - 生成避免碰撞的电路图

### 第三部分：position_recorder.py

- **功能**：记录器件的最终位置和大小，生成新的 JSON 文件
- **特性**：
  - 记录完整的布局信息
  - 生成布局统计报告
  - 计算布局密度和最优位置达成率
  - 输出多种格式的文件
  - **生成 YOLO 格式标注**：支持目标检测模型训练

### 主脚本：main.py

- **功能**：协调运行三个部分，管理整个布局流程
- **特性**：
  - 自动查找 JSON 文件
  - 验证输入文件格式
  - 生成完整的输出报告
  - 所有文件保存在 data 文件夹中

## 使用方法

### 1. 准备 JSON 文件

确保有包含电路信息的 JSON 文件（如`example1_netlist.json`或`example2_netlist.json`）。

JSON 文件应包含以下结构：

```json
{
  "chip": {
    "model": "芯片型号",
    "pin_count": 8,
    "schemdraw_params": {
      "spacing": 1.5,
      "pad": 1.5,
      "leadlen": 0.3
    }
  },
  "components": [
    {
      "id": "R1",
      "type": "resistor",
      "value": "10k",
      "schemdraw_params": {
        "length": 3.0,
        "theta": 0
      }
    }
  ],
  "nets": [...]
}
```

### 2. 运行主脚本

```bash
cd data
python main.py
```

主脚本会自动：

1. 查找 JSON 文件
2. 验证文件格式
3. 运行三个部分的处理流程
4. 生成所有输出文件

### 3. 单独运行各部分

#### 运行第一部分（基础绘图）：

```bash
python json_reader_and_drawer.py
```

#### 运行第二部分（碰撞检测）：

```bash
python collision_detector.py
```

#### 运行第三部分（位置记录）：

```bash
python position_recorder.py
```

## 输出文件

运行完成后，data 文件夹中会生成以下文件：

1. **basic_circuit.png** - 基础电路图（未经碰撞检测）
2. **collision_free_circuit.png** - 避免碰撞的最终电路图
3. **complete_layout.json** - 完整的布局信息 JSON 文件
4. **component_coordinates.json** - 简化的组件坐标信息
5. **layout_summary.txt** - 布局摘要报告
6. **yolo_annotations.txt** - YOLO 格式的标注文件
7. **yolo_classes.txt** - YOLO 类别映射文件
8. **yolo_dataset_info.json** - YOLO 数据集详细信息

## JSON 参数说明

### 芯片参数 (chip.schemdraw_params)

- `spacing`: 引脚间距
- `pad`: 内边距
- `leadlen`: 引脚长度

### 组件参数 (component.schemdraw_params)

- `length`: 组件长度
- `width`: 组件宽度
- `theta`: 旋转角度（度）
- `loops`: 电阻的锯齿数量
- `radius`: 电压源的半径

### 布局尺寸 (layout_size)

- `width`: 布局宽度
- `height`: 布局高度

## 依赖库

- `schemdraw`: 电路图绘制
- `json`: JSON 文件处理
- `math`: 数学计算
- `datetime`: 时间戳生成
- `typing`: 类型提示

## 注意事项

1. 确保所有 Python 文件都在同一目录中
2. JSON 文件应放在 data 目录或其父目录中
3. 生成的图片文件为 PNG 格式
4. 坐标系统以芯片为中心（0,0）
5. 器件位置会根据连接关系自动优化

## 错误处理

系统包含完善的错误处理机制：

- 文件不存在检查
- JSON 格式验证
- 导入模块检查
- 碰撞检测失败处理

如果遇到问题，请检查：

1. JSON 文件格式是否正确
2. 所有必要的 Python 库是否已安装
3. 文件权限是否正确

## YOLO 格式标注说明

系统自动生成符合 YOLO 目标检测格式的标注文件：

### YOLO 标注格式

每个对象一行，格式为：

```
<class_id> <x_center> <y_center> <width> <height>
```

- `class_id`: 类别编号（从 0 开始）
- `x_center`: 边界框中心 X 坐标（归一化，0-1）
- `y_center`: 边界框中心 Y 坐标（归一化，0-1）
- `width`: 边界框宽度（归一化，0-1）
- `height`: 边界框高度（归一化，0-1）

### 生成的 YOLO 文件

1. **yolo_annotations.txt** - 标注数据

   - 每行代表一个检测对象
   - 包括芯片和所有组件
   - 坐标已归一化到画布尺寸

2. **yolo_classes.txt** - 类别映射

   - 按字母顺序排列的类别名称
   - 行号对应 class_id

3. **yolo_dataset_info.json** - 数据集信息
   - 画布尺寸和坐标系信息
   - 类别统计和分布
   - 边界框大小范围

### 坐标系转换

- 原始坐标：以芯片为中心(0,0)，Y 轴向上
- YOLO 坐标：左上角为原点(0,0)，Y 轴向下，归一化到 0-1

### 使用建议

- 可直接用于 YOLO 模型训练
- 配合对应的电路图片使用
- 类别映射保持一致性，便于多图片数据集

## 扩展功能

可以通过修改相应的脚本来扩展功能：

- 添加新的器件类型
- 修改碰撞检测算法
- 自定义输出格式
- 调整布局策略
- 扩展 YOLO 标注功能（如添加关键点检测）
