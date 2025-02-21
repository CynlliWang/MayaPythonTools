import maya.cmds as cmds
import math


generated_curve = None
original_vertices = []
is_closed_curve = False
selected_edges = None

"""
曲线创建
"""



def generateCurve():
    global generated_curve, original_vertices, is_closed_curve, selected_edges
    try:
        # 清理旧数据
        if generated_curve and cmds.objExists(generated_curve):
            cmds.delete(generated_curve)
        generated_curve = None
        original_vertices = []

        # 获取选择
        selected_edges = cmds.ls(sl=True, fl=True)
        if not selected_edges:
            cmds.warning("请选择多边形边界边")
            return

        # 创建曲线（用于自动检测闭合）
        curve_shape = cmds.polyToCurve(
            form=2,  #自动检测闭合
            degree=3, #1保持曲线cv点不偏移,3则自动平滑3次方
            ch=0
        )[0]
        
        is_closed_curve = cmds.getAttr(curve_shape+".form") == 2
        
        '''

        # 重建曲线，增加cv点
        cmds.rebuildCurve(
            curve_shape,
            spans=cmds.getAttr(f"{curve_shape}.spans")*3,
            keepRange=0,
            degree=3
        )
        '''
        cmds.select(curve_shape)  # 选中新建的曲线
        cmds.xform(cmds.ls(selection=True), centerPivots=True) # 居中枢轴
        generated_curve = curve_shape
        
        
        
        # 获取原始顶点（保留顺序）
        vertices = cmds.polyListComponentConversion(selected_edges, fromEdge=True, toVertex=True)
        original_vertices = cmds.ls(vertices, fl=True)

        cmds.inViewMessage(assistMessage=f"曲线创建成功: {curve_shape}", position='topCenter', fade=True)
        return True

    except Exception as e:
        cmds.warning(f"曲线创建失败: {str(e)}")
        return False


"""
平滑板块
"""
def custom_smooth_curve(smooth_iterations=2, tension=0.5):
    global generated_curve, is_closed_curve
    
    if not cmds.objExists(generated_curve):
        cmds.warning("请先创建有效曲线")
        return
    
    cvs = cmds.ls(f"{generated_curve}.cv[*]", fl=True)
    cv_count = len(cvs)
    if cv_count < 3:
        cmds.warning("需要至少3个CV点进行平滑")
        return
    
    # 存储开放曲线端点坐标
    original_first_pos = cmds.pointPosition(cvs[0]) if not is_closed_curve else None
    original_last_pos = cmds.pointPosition(cvs[-1]) if not is_closed_curve else None
    
    for _ in range(smooth_iterations):
        new_positions = []
        current_positions = [cmds.pointPosition(cv) for cv in cvs]  # 批量获取坐标
        
        for i in range(cv_count):
            # 开放曲线端点锁定
            if not is_closed_curve and (i == 0 or i == cv_count-1):
                new_positions.append(current_positions[i])
                continue
                
            # 自动计算相邻索引（支持闭合环形访问）
            prev_index = (i - 1) % cv_count
            next_index = (i + 1) % cv_count
            
            prev_pos = current_positions[prev_index]
            current_pos = current_positions[i]
            next_pos = current_positions[next_index]
            
            # 优化后的平滑公式
            new_x = (prev_pos[0] + (2 + tension)*current_pos[0] + next_pos[0]) / (4 + tension)
            new_y = (prev_pos[1] + (2 + tension)*current_pos[1] + next_pos[1]) / (4 + tension)
            new_z = (prev_pos[2] + (2 + tension)*current_pos[2] + next_pos[2]) / (4 + tension)
            
            new_positions.append((new_x, new_y, new_z))
        
        # 批量更新坐标（优化性能）
        for i, pos in enumerate(new_positions):
            cmds.xform(cvs[i], t=pos, ws=True)
    
    # 开放曲线恢复端点（防止浮点误差）
    if not is_closed_curve:
        cmds.xform(cvs[0], t=original_first_pos, ws=True)
        cmds.xform(cvs[-1], t=original_last_pos, ws=True)
    
    cmds.inViewMessage(assistMessage=f"高级平滑完成 (迭代:{smooth_iterations})", position='topCenter', fade=True)
"""
边长平均
"""

def average_edge_length_system():
    """
    高效边长平均化系统
    流程说明：
    1. 创建临时线性曲线
    2. 重建曲线获得均匀分布CV点
    3. 将顶点吸附到对应CV点
    4. 自动清理临时数据
    """
    global original_vertices,selected_edges,generated_curve
    temp_curve = None  # 初始化变量
    try:
        
        # 少于3条边则跳过
        if len(selected_edges) <3: return
        
        
        if selected_edges:
            cmds.select(selected_edges, replace=True)
        # 步骤1：创建初始线性曲线
        
        temp_curve = cmds.polyToCurve(
            form=2,  # 自动检测闭合
            degree=1, 
            ch=0  # 关闭构建历史
        )[0]
        
        # 步骤2：获取所有CV点坐标（四舍五入到小数点后三位）
        cvs = cmds.ls(f"{temp_curve}.cv[*]", fl=True)
        # === 阶段3：建立映射关系（重建前）===
        
        cv_index_map = {}  # 存储cv索引的绝对位置映射
        for i, cv in enumerate(cvs):
            pos = cmds.xform(cv, q=True, ws=True, t=True)
            key = tuple(round(x, 3) for x in pos)
            cv_index_map[key] = i  # 记录原始位置对应的索引
        
        # 建立顶点到cv索引的映射
        vert_cv_indices = {}
        for vert in original_vertices:
            raw_pos = cmds.xform(vert, q=True, ws=True, t=True)
            round_pos = tuple(round(x, 3) for x in raw_pos)
            if round_pos in cv_index_map:
                vert_cv_indices[vert] = cv_index_map[round_pos]
                
        # === 阶段4：重建曲线 === 
        cmds.rebuildCurve(temp_curve, ch=0, rpo=1, rt=0, end=1, kr=0, kcp=0, kep=1, kt=0, s=0, d=1, tol=0)
        
        # === 阶段5：获取重建后的cv位置 ===
        new_cv_positions = [cmds.xform(cv, q=True, ws=True, t=True) for cv in cvs]
        
        # === 阶段6：应用新位置 ===
        update_count = 0
        for vert, cv_index in vert_cv_indices.items():
            if cv_index < len(new_cv_positions):
                cmds.xform(vert, t=new_cv_positions[cv_index], ws=True)
                update_count += 1

        
        # === 结果反馈 ===
        success_rate = round(update_count/len(original_vertices)*100, 1)
        cmds.inViewMessage(assistMessage=f"顶点更新完成 ({success_rate}%)", 
                         position='topCenter', 
                         fade=True)
        
    except Exception as e:
        cmds.warning(f"操作失败: {str(e)}")
        cmds.inViewMessage(assistMessage="边长平均化失败", 
                         position='topCenter', 
                         fade=True,
                         status="Error")

    finally:
        # === 清理资源 ===
        if temp_curve and cmds.objExists(temp_curve):
            cmds.delete(temp_curve)


"""
顶点吸附
"""


def distance(pos1, pos2):
    return math.sqrt(sum((a - b)**2 for a, b in zip(pos1, pos2)))

def snapVertices():
    global generated_curve, original_vertices,selected_edges
    try:

        
        
        # 原生代码
        if not generated_curve or not original_vertices:
            cmds.warning("缺少必要数据")
            return False


        '''
        '''
        
        
        # 重建曲线，增加cv点
        cmds.rebuildCurve(
            generated_curve,
            spans=len(original_vertices)*3,
            keepRange=0,
            degree=3
        )





        # 获取所有CV点位置
        cvs = cmds.ls(f"{generated_curve}.cv[*]", fl=True)
        cv_positions = [cmds.pointPosition(cv) for cv in cvs]

        # 最近点算法
        for vtx in original_vertices:
            if not cmds.objExists(vtx):
                continue
            vtx_pos = cmds.pointPosition(vtx)
            closest_pos = min(cv_positions, key=lambda x: distance(vtx_pos, x))
            cmds.xform(vtx, t=closest_pos, ws=True)
        

        cmds.inViewMessage(assistMessage="顶点吸附完成", position='topCenter', fade=True)
        return True

    except Exception as e:
        cmds.warning(f"吸附失败: {str(e)}")
        return False
    


"""
平滑优化板块
"""



def shape_preserving_smooth(smooth_iterations=2, tension=0.5, preserve_strength=0.3):
    """
    形状保持型平滑算法
    参数：
    smooth_iterations - 迭代次数
    tension - 张力系数（0.0-1.0）
    preserve_strength - 形状保持强度（0.0-1.0）
    """
    global generated_curve, is_closed_curve
    
    if not cmds.objExists(generated_curve):
        cmds.warning("请先创建有效曲线")
        return
    
    cvs = cmds.ls(f"{generated_curve}.cv[*]", fl=True)
    cv_count = len(cvs)
    if cv_count < 3:
        cmds.warning("需要至少3个CV点进行平滑")
        return
    
    # 存储原始坐标和初始特征量
    original_positions = [cmds.pointPosition(cv) for cv in cvs]
    original_length = calculate_curve_length(cvs, is_closed_curve)
    
    for _ in range(smooth_iterations):
        new_positions = []
        current_positions = [cmds.pointPosition(cv) for cv in cvs]
        
        for i in range(cv_count):
            if not is_closed_curve and (i == 0 or i == cv_count-1):
                new_positions.append(current_positions[i])
                continue
                
            # 计算标准平滑位置
            prev_index, next_index = get_adjacent_indices(i, cv_count, is_closed_curve)
            prev_pos = current_positions[prev_index]
            current_pos = current_positions[i]
            next_pos = current_positions[next_index]
            
            smoothed_pos = (
                (prev_pos[0] + (2 + tension)*current_pos[0] + next_pos[0]) / (4 + tension),
                (prev_pos[1] + (2 + tension)*current_pos[1] + next_pos[1]) / (4 + tension),
                (prev_pos[2] + (2 + tension)*current_pos[2] + next_pos[2]) / (4 + tension)
            )
            
            # 计算形状保持补偿
            original_offset = (
                original_positions[i][0] - smoothed_pos[0],
                original_positions[i][1] - smoothed_pos[1],
                original_positions[i][2] - smoothed_pos[2]
            )
            
            # 应用补偿
            compensated_pos = (
                smoothed_pos[0] + original_offset[0] * preserve_strength,
                smoothed_pos[1] + original_offset[1] * preserve_strength,
                smoothed_pos[2] + original_offset[2] * preserve_strength
            )
            
            new_positions.append(compensated_pos)
        
        # 更新坐标并保持闭合性
        update_positions(cvs, new_positions, is_closed_curve)
        
        # 长度补偿（可选）
        current_length = calculate_curve_length(cvs, is_closed_curve)
        scale_factor = original_length / current_length if current_length > 0 else 1
        scale_curve(cvs, scale_factor, is_closed_curve)
    
    cmds.inViewMessage(assistMessage=f"形状保持平滑完成 (强度:{preserve_strength})", position='topCenter', fade=True)

# 辅助函数
def get_adjacent_indices(i, count, is_closed):
    if is_closed:
        return (i-1)%count, (i+1)%count
    return max(0,i-1), min(count-1,i+1)

# 在 calculate_curve_length 函数中替换 math.dist 的调用
def calculate_curve_length(cvs, is_closed):
    total = 0
    for i in range(len(cvs)):
        next_index = (i+1)%len(cvs) if is_closed else i+1
        if next_index >= len(cvs):
            break
        # 手动计算欧氏距离（Python 2 无 math.dist）
        pos1 = cmds.pointPosition(cvs[i])
        pos2 = cmds.pointPosition(cvs[next_index])
        total += math.sqrt(sum((a-b)**2 for a, b in zip(pos1, pos2)))
    return total

# 在 scale_curve 函数中修复整数除法问题
def scale_curve(cvs, factor, is_closed):
    if factor == 1:
        return
    
    # 计算几何中心时确保浮点运算
    positions = [cmds.pointPosition(cv) for cv in cvs]
    center = [
        sum(p[0] for p in positions)/float(len(positions)),
        sum(p[1] for p in positions)/float(len(positions)),
        sum(p[2] for p in positions)/float(len(positions))
    ]
    
    # 缩放逻辑保持不变
    for i, cv in enumerate(cvs):
        if not is_closed and (i == 0 or i == len(cvs)-1):
            continue
        pos = cmds.pointPosition(cv)
        new_pos = [
            center[0] + (pos[0]-center[0])*factor,
            center[1] + (pos[1]-center[1])*factor,
            center[2] + (pos[2]-center[2])*factor
        ]
        cmds.xform(cv, t=new_pos, ws=True)




"""
    # 一键处理流程
"""



def autoSmoothProcess():
    
    global selected_edges
    
    #f(0 if len(selected_edges) > 50 else 0.5)


    generateCurve()
    custom_smooth_curve(smooth_iterations=5 if len(selected_edges) > 50 else 10,tension=0 if len(selected_edges) > 50 else 0.5)
    # shape_preserving_smooth(1,0.5,0.7)
#    average_edge_length_system()
    snapVertices()
#    average_edge_length_system()
    if cmds.objExists(generated_curve):
        cmds.delete(generated_curve)
    
    
    cmds.inViewMessage(assistMessage='一键流程完成', position='topCenter', fade=True)
    
    if selected_edges:
        cmds.select(selected_edges, replace=True)



"""
# UI部分
"""

def createUI():
    if cmds.window('edgeSmoothTool', exists=True):
        cmds.deleteUI('edgeSmoothTool')
    
    cmds.window('edgeSmoothTool', title="平滑边工具", width=350)
    main_layout = cmds.columnLayout(adjustableColumn=True)
    

    # 调试信息区
    cmds.separator(h=10, style="none")
    cmds.text(label="请选择连续边后执行操作",font="boldLabelFont",h=20)
    cmds.separator(h=10, style="none")


    
    cmds.frameLayout(label="自动流程", collapsable=True)
    cmds.columnLayout(adjustableColumn=True)
    
    cmds.button(label="一键平滑边", command=lambda _: autoSmoothProcess(), h=45, bgc=(0.2,0.5,0.2))

    cmds.separator(h=15, style="none")
    cmds.button(label="平均划分记录的边", annotation="平均划分多边形边", command=lambda _: average_edge_length_system(), h=25, bgc=(0.2,0.4,0.2))
    cmds.separator(h=10, style="none")
    
    cmds.setParent("..")
    cmds.setParent("..")
    
    
    # 在分步操作区添加参数控制
    # 修改后的参数控制部分
    cmds.frameLayout(label="手动流程", 
                   borderVisible=True,
                   marginWidth=10,
                   backgroundColor=(0.15, 0.15, 0.15),
                   collapsable=True,cl=1
                   )



    # 分步操作
    cmds.text(label="分步控制", font="boldLabelFont")
    
    # 第一步
    cmds.button(label="1. 记录选择边并生成曲线", annotation="从选择边创建曲线", command=lambda _: generateCurve(),backgroundColor=(0.0, 0.3, 0))
 
 
    # 第二步
    # 迭代次数滑块
    cmds.intSliderGrp("iter_slider",
                label="迭代次数",
                field=True,
                minValue=1,
                maxValue=10,
                value=5)
    

    # 张力系数滑块
    cmds.floatSliderGrp("tension_slider",
                      label="细节保留度",
                      field=True,
                      minValue=0.0,
                      maxValue=1.0,
                      value=0.1)
    

        # 添加预设按钮
    PRESETS = {
        "强": (10, 0.1),
        "中": (3, 0.5),
        "弱": (2, 0.9)
    }

    def apply_preset(preset_name):
        params = PRESETS[preset_name]
        cmds.intSliderGrp("iter_slider", e=True, value=params[0])
        cmds.floatSliderGrp("tension_slider", e=True, value=params[1])
        #cmds.floatSliderGrp("preserve_slider", e=True, value=params[2])

    # 在UI中添加预设按钮
    cmds.optionMenu(label="预设", changeCommand=lambda x: apply_preset(x))
    for name in PRESETS:
        cmds.menuItem(label=name)



    cmds.button(label="2. 平滑曲线（可多次迭代）", 
                command=lambda _: custom_smooth_curve(
                cmds.intSliderGrp("iter_slider", q=True, value=True),
                cmds.floatSliderGrp("tension_slider", q=True, value=True)
                ),backgroundColor=(0.0, 0.3, 0)
                )
                

#    # 在UI中添加控制项
#    cmds.floatSliderGrp("preserve_slider", 
#                       label="形状保持", 
#                      minValue=0.0, 
#                       maxValue=1.0, 
#                       value=0.3)




#    # 修改按钮命令
#    cmds.button(label="2.1 抵消曲线平滑时收缩效果（可选）", 
#              command=lambda _: shape_preserving_smooth(
#                  cmds.intSliderGrp("iter_slider", q=True, value=True),
#                  cmds.floatSliderGrp("tension_slider", q=True, value=True),
#                  cmds.floatSliderGrp("preserve_slider", q=True, value=True)))


    
    
    # 第三步
    cmds.button(label="3. 边吸附到曲线", annotation="将顶点吸附到曲线", command=lambda _: snapVertices(),backgroundColor=(0.0, 0.3, 0))
        
        
        

    # 第四步
    cmds.button(label="4. 清理曲线", annotation="删除生成的曲线", backgroundColor=(0.5, 0.2, 0.2), command=lambda _: cmds.delete(generated_curve))
    
    
    # 结束
    cmds.setParent("..")
    cmds.setParent("..")
    
    
     
    cmds.showWindow()

createUI()