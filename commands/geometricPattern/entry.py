import os
import math
import traceback
from typing import List, Tuple, Optional

import adsk.core
import adsk.fusion

from ...lib import fusionAddInUtils as futil
from ... import config
from .pattern_engine import (
    PatternItem,
    FaceCoordinateFrame,
    generate_geometric_pattern
)

app = adsk.core.Application.get()
ui = app.userInterface if app else None

CMD_NAME = 'Geometric Pattern'
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_geometric_pattern'
CMD_DESCRIPTION = 'Create variable-density geometric patterns and vents on planar faces'
IS_PROMOTED = True

WORKSPACE_ID = config.design_workspace
PANEL_ID = config.pattern_panel_id

RESOURCE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources')

local_handlers = []
_active_cg_group: Optional[adsk.fusion.CustomGraphicsGroup] = None


def get_icon_path(subfolder: str) -> str:
    """Returns valid icon directory path for button row items."""
    target = os.path.join(RESOURCE_DIR, subfolder)
    if os.path.isdir(target):
        return target
    return RESOURCE_DIR


def start():
    """Register command definition and add toolbar button."""
    try:
        cmd_def = ui.commandDefinitions.itemById(CMD_ID)
        if not cmd_def:
            cmd_def = ui.commandDefinitions.addButtonDefinition(
                CMD_ID, CMD_NAME, CMD_DESCRIPTION, RESOURCE_DIR
            )

        futil.add_handler(cmd_def.commandCreated, command_created)

        workspace = ui.workspaces.itemById(WORKSPACE_ID)
        if workspace:
            panel = workspace.toolbarPanels.itemById(PANEL_ID)
            if not panel:
                tab = workspace.toolbarTabs.itemById(config.design_tab_id)
                if tab:
                    panel = tab.toolbarPanels.itemById(PANEL_ID)
            if panel:
                control = panel.controls.itemById(CMD_ID)
                if not control:
                    control = panel.controls.addCommand(cmd_def)
                    control.isPromoted = IS_PROMOTED
    except:
        futil.handle_error('start')


def stop():
    """Remove toolbar button and clean up command definition."""
    try:
        cleanup_preview_graphics()

        workspace = ui.workspaces.itemById(WORKSPACE_ID)
        if workspace:
            panel = workspace.toolbarPanels.itemById(PANEL_ID)
            if not panel:
                tab = workspace.toolbarTabs.itemById(config.design_tab_id)
                if tab:
                    panel = tab.toolbarPanels.itemById(PANEL_ID)
            if panel:
                control = panel.controls.itemById(CMD_ID)
                if control:
                    control.deleteMe()

        cmd_def = ui.commandDefinitions.itemById(CMD_ID)
        if cmd_def:
            cmd_def.deleteMe()
    except:
        futil.handle_error('stop')


def command_created(args: adsk.core.CommandCreatedEventArgs):
    """Build the Geometric Pattern command dialog matching the screenshot."""
    try:
        cmd = args.command
        cmd.isExecutedWhenPreEmpted = False

        # Connect event handlers
        futil.add_handler(cmd.execute, command_execute, local_handlers=local_handlers)
        futil.add_handler(cmd.executePreview, command_preview, local_handlers=local_handlers)
        futil.add_handler(cmd.inputChanged, command_input_changed, local_handlers=local_handlers)
        futil.add_handler(cmd.validateInputs, command_validate_input, local_handlers=local_handlers)
        futil.add_handler(cmd.destroy, command_destroy, local_handlers=local_handlers)

        inputs = cmd.commandInputs

        # 1. Face Selection Input
        face_selection = inputs.addSelectionInput(
            'face_selection', 'Face', 'Select a planar face'
        )
        face_selection.addSelectionFilter('PlanarFaces')
        face_selection.setSelectionLimits(1, 1)

        # 2. Object Type Button Row
        obj_type = inputs.addButtonRowCommandInput('obj_type', 'Object Type', False)
        obj_type.listItems.add('Circle / Hole', True, get_icon_path('type_circle'))
        obj_type.listItems.add('Cylinder', False, get_icon_path('type_cylinder'))
        obj_type.listItems.add('Box', False, get_icon_path('type_box'))
        obj_type.listItems.add('Hexagon', False, get_icon_path('type_hex'))

        # 3. Object Size Group
        size_group = inputs.addGroupCommandInput('size_group', 'Object Size')
        size_group.isExpanded = True
        size_inputs = size_group.children

        size_inputs.addValueInput(
            'size_limit_1', 'Size Limit 1', 'mm',
            adsk.core.ValueInput.createByString('6.00 mm')
        )
        size_inputs.addValueInput(
            'size_limit_2', 'Size Limit 2', 'mm',
            adsk.core.ValueInput.createByString('2.00 mm')
        )

        spread_input = size_inputs.addFloatSliderCommandInput(
            'spread', 'Spread', '', -1.0, 1.0, False
        )
        spread_input.valueOne = -0.60
        spread_input.setText('-1.00', '+1.00')

        gradient_axis = size_inputs.addDropDownCommandInput(
            'gradient_axis', 'Gradient', adsk.core.DropDownStyles.TextListDropDownStyle
        )
        gradient_axis.listItems.add('Radial (Center)', True)
        gradient_axis.listItems.add('U-Axis', False)
        gradient_axis.listItems.add('V-Axis', False)

        # 4. Object Distribution Group
        dist_group = inputs.addGroupCommandInput('dist_group', 'Object Distribution')
        dist_group.isExpanded = True
        dist_inputs = dist_group.children

        dist_type = dist_inputs.addButtonRowCommandInput('dist_type', 'Distribution Type', False)
        dist_type.listItems.add('Triangular', True, get_icon_path('dist_triangular'))
        dist_type.listItems.add('Grid', False, get_icon_path('dist_grid'))
        dist_type.listItems.add('Hexagonal', False, get_icon_path('dist_hex'))
        dist_type.listItems.add('Radial', False, get_icon_path('dist_radial'))

        dist_inputs.addValueInput(
            'distance', 'Distance', 'mm',
            adsk.core.ValueInput.createByString('14.80 mm')
        )

        u_align = dist_inputs.addButtonRowCommandInput('u_alignment', 'U Alignment', False)
        u_align.listItems.add('Left', False, get_icon_path('u_left'))
        u_align.listItems.add('Center', True, get_icon_path('u_center'))
        u_align.listItems.add('Right', False, get_icon_path('u_right'))

        v_align = dist_inputs.addButtonRowCommandInput('v_alignment', 'V Alignment', False)
        v_align.listItems.add('Bottom', False, get_icon_path('v_bottom'))
        v_align.listItems.add('Center', True, get_icon_path('v_center'))
        v_align.listItems.add('Top', False, get_icon_path('v_top'))

        dist_inputs.addBoolValueInput(
            'clear_perimeter', 'Clear Perimeter', True, '', True
        )
        dist_inputs.addValueInput(
            'perimeter_margin', 'Margin', 'mm',
            adsk.core.ValueInput.createByString('0.50 mm')
        )

        # 5. Operation Group
        op_group = inputs.addGroupCommandInput('op_group', 'Operation')
        op_group.isExpanded = True
        op_inputs = op_group.children

        op_input = op_inputs.addDropDownCommandInput(
            'operation', 'Operation', adsk.core.DropDownStyles.TextListDropDownStyle
        )
        op_input.listItems.add('Cut', True)
        op_input.listItems.add('Join', False)
        op_input.listItems.add('New Body', False)
        op_input.listItems.add('Sketch Only', False)

        op_inputs.addValueInput(
            'extrude_depth', 'Extrude Depth', 'mm',
            adsk.core.ValueInput.createByString('5.00 mm')
        )

        # 6. Status Text
        status_box = inputs.addTextBoxCommandInput(
            'status_box', '', '<small style="color: #666;">Select a planar face to generate geometric pattern.</small>', 2, True
        )
        status_box.isFullWidth = True

    except:
        futil.handle_error('command_created')


def extract_face_data(face: adsk.fusion.BRepFace) -> Optional[Tuple[FaceCoordinateFrame, List[Tuple[float, float]], List[List[Tuple[float, float]]]]]:
    """Extracts FaceCoordinateFrame and outer/inner 2D polygon loops in UV coordinates."""
    try:
        if not face or not face.isValid:
            return None

        plane = face.geometry
        if not isinstance(plane, adsk.core.Plane):
            return None

        origin_pt = plane.origin
        normal = plane.normal

        # Construct orthonormal UV basis on the plane
        if abs(normal.z) < 0.85:
            ref_vec = adsk.core.Vector3D.create(0, 0, 1)
        elif abs(normal.x) < 0.85:
            ref_vec = adsk.core.Vector3D.create(1, 0, 0)
        else:
            ref_vec = adsk.core.Vector3D.create(0, 1, 0)

        u_vec = ref_vec.crossProduct(normal)
        u_vec.normalize()
        v_vec = normal.crossProduct(u_vec)
        v_vec.normalize()

        frame = FaceCoordinateFrame(
            origin=(origin_pt.x, origin_pt.y, origin_pt.z),
            u_dir=(u_vec.x, u_vec.y, u_vec.z),
            v_dir=(v_vec.x, v_vec.y, v_vec.z),
            normal=(normal.x, normal.y, normal.z)
        )

        outer_poly: List[Tuple[float, float]] = []
        inner_polys: List[List[Tuple[float, float]]] = []

        for loop in face.loops:
            loop_pts_uv: List[Tuple[float, float]] = []
            for edge in loop.edges:
                # Add edge start vertex
                sv = edge.startVertex
                if sv:
                    pt = sv.geometry
                    loop_pts_uv.append(frame.to_uv((pt.x, pt.y, pt.z)))

                # Sample intermediate points along non-linear curves
                try:
                    evaluator = edge.evaluator
                    res, sp, ep = evaluator.getParameterExtents()
                    if res and abs(ep - sp) > 1e-5:
                        for k in range(1, 6):
                            t = sp + (ep - sp) * (k / 6.0)
                            ok, pt = evaluator.getPointAtParameter(t)
                            if ok and pt:
                                loop_pts_uv.append(frame.to_uv((pt.x, pt.y, pt.z)))
                except:
                    pass

                ev = edge.endVertex
                if ev:
                    pt = ev.geometry
                    loop_pts_uv.append(frame.to_uv((pt.x, pt.y, pt.z)))

            if len(loop_pts_uv) >= 3:
                if loop.isOuter:
                    outer_poly = loop_pts_uv
                else:
                    inner_polys.append(loop_pts_uv)

        # Fallback if outer loop was ambiguous
        if not outer_poly and inner_polys:
            outer_poly = max(
                inner_polys,
                key=lambda p: (max(x[0] for x in p) - min(x[0] for x in p)) * (max(x[1] for x in p) - min(x[1] for x in p))
            )
            inner_polys.remove(outer_poly)

        if len(outer_poly) < 3:
            outer_poly = [frame.to_uv((v.geometry.x, v.geometry.y, v.geometry.z)) for v in face.vertices]

        return frame, outer_poly, inner_polys
    except:
        return None


def calculate_pattern_from_inputs(inputs: adsk.core.CommandInputs) -> Tuple[Optional[FaceCoordinateFrame], List[PatternItem], str]:
    """Reads all dialog inputs safely and computes pattern items."""
    try:
        face_input: Optional[adsk.core.SelectionCommandInput] = inputs.itemById('face_selection')
        if not face_input or face_input.selectionCount == 0:
            return None, [], 'Please select a planar face.'

        selected_face: adsk.fusion.BRepFace = face_input.selection(0).entity
        face_data = extract_face_data(selected_face)
        if not face_data:
            return None, [], 'Selected face is not a valid planar face.'

        frame, outer_poly, inner_polys = face_data
        if len(outer_poly) < 3:
            return frame, [], 'Could not determine face boundary.'

        def get_val(input_id: str, default: float) -> float:
            inp = inputs.itemById(input_id)
            if inp and hasattr(inp, 'value'):
                return inp.value
            return default

        size_1 = max(0.01, get_val('size_limit_1', 0.60))
        size_2 = max(0.01, get_val('size_limit_2', 0.20))
        distance = max(0.05, get_val('distance', 1.48))
        margin = max(0.0, get_val('perimeter_margin', 0.05))

        spread_inp: Optional[adsk.core.FloatSliderCommandInput] = inputs.itemById('spread')
        spread = spread_inp.valueOne if spread_inp else -0.60

        clear_inp: Optional[adsk.core.BoolValueCommandInput] = inputs.itemById('clear_perimeter')
        clear_perim = clear_inp.value if clear_inp else True

        def get_selected(input_id: str, default: str) -> str:
            inp = inputs.itemById(input_id)
            if inp and hasattr(inp, 'selectedItem') and inp.selectedItem:
                return inp.selectedItem.name.upper()
            return default.upper()

        dist_type_str = get_selected('dist_type', 'TRIANGULAR')
        if 'GRID' in dist_type_str or 'RECT' in dist_type_str:
            dist_type = 'RECTANGULAR'
        elif 'HEX' in dist_type_str:
            dist_type = 'HEXAGONAL'
        elif 'RADIAL' in dist_type_str:
            dist_type = 'RADIAL'
        else:
            dist_type = 'TRIANGULAR'

        grad_axis_str = get_selected('gradient_axis', 'RADIAL')
        if 'U-AXIS' in grad_axis_str:
            grad_axis = 'U_AXIS'
        elif 'V-AXIS' in grad_axis_str:
            grad_axis = 'V_AXIS'
        else:
            grad_axis = 'RADIAL'

        obj_type_str = get_selected('obj_type', 'CIRCLE')
        if 'BOX' in obj_type_str or 'SQUARE' in obj_type_str:
            obj_type = 'BOX'
        elif 'HEX' in obj_type_str:
            obj_type = 'HEXAGON'
        else:
            obj_type = 'CIRCLE'

        u_align = get_selected('u_alignment', 'CENTER')
        v_align = get_selected('v_alignment', 'CENTER')

        items = generate_geometric_pattern(
            outer_poly=outer_poly,
            inner_polys=inner_polys,
            distribution_type=dist_type,
            object_type=obj_type,
            size_limit_1=size_1,
            size_limit_2=size_2,
            spread=spread,
            distance=distance,
            u_alignment=u_align,
            v_alignment=v_align,
            clear_perimeter=clear_perim,
            perimeter_margin=margin,
            gradient_axis=grad_axis
        )

        for item in items:
            item.world_center = frame.to_3d(item.u, item.v)

        status_msg = f'Generated {len(items)} elements | Pitch: {distance*10:.1f} mm | Range: {size_2*10:.2f} - {size_1*10:.2f} mm'
        return frame, items, status_msg

    except:
        return None, [], f'Calculation error: {traceback.format_exc()}'


def cleanup_preview_graphics():
    """Safely removes any active custom preview graphics group."""
    global _active_cg_group
    try:
        if _active_cg_group and _active_cg_group.isValid:
            _active_cg_group.deleteMe()
        _active_cg_group = None
    except:
        pass


def update_preview_graphics(frame: Optional[FaceCoordinateFrame], items: List[PatternItem]):
    """Renders lightweight custom graphics directly in the viewport."""
    global _active_cg_group
    cleanup_preview_graphics()

    if not items or not frame:
        return

    try:
        app = adsk.core.Application.get()
        des = adsk.fusion.Design.cast(app.activeProduct)
        if not des:
            return

        root = des.rootComponent
        cg_group = root.customGraphicsGroups.add()
        _active_cg_group = cg_group

        normal_vec = adsk.core.Vector3D.create(frame.normal[0], frame.normal[1], frame.normal[2])
        color_cyan = adsk.core.Color.create(0, 180, 255, 220)
        solid_color = adsk.fusion.CustomGraphicsSolidColorEffect.create(color_cyan)

        for item in items:
            if not item.world_center:
                continue

            cx, cy, cz = item.world_center
            center_pt = adsk.core.Point3D.create(cx, cy, cz)

            if item.shape_type == 'box':
                half_s = item.radius
                u_dir = adsk.core.Vector3D.create(frame.u_dir[0], frame.u_dir[1], frame.u_dir[2])
                v_dir = adsk.core.Vector3D.create(frame.v_dir[0], frame.v_dir[1], frame.v_dir[2])
                u_dir.scaleBy(half_s)
                v_dir.scaleBy(half_s)

                p1 = center_pt.copy()
                p1.translateBy(u_dir)
                p1.translateBy(v_dir)

                p2 = center_pt.copy()
                u_neg = u_dir.copy()
                u_neg.scaleBy(-1.0)
                p2.translateBy(u_neg)
                p2.translateBy(v_dir)

                p3 = center_pt.copy()
                v_neg = v_dir.copy()
                v_neg.scaleBy(-1.0)
                p3.translateBy(u_neg)
                p3.translateBy(v_neg)

                p4 = center_pt.copy()
                p4.translateBy(u_dir)
                p4.translateBy(v_neg)

                coords = [p1.x, p1.y, p1.z, p2.x, p2.y, p2.z, p3.x, p3.y, p3.z, p4.x, p4.y, p4.z]
                indices = [0, 1, 1, 2, 2, 3, 3, 0]
                cg_coords = adsk.fusion.CustomGraphicsCoordinates.create(coords)
                cg_lines = cg_group.addLines(cg_coords, indices, False)
                cg_lines.color = solid_color
                cg_lines.weight = 2.0
            elif item.shape_type == 'hexagon':
                coords = []
                indices = []
                for k in range(6):
                    ang = k * (math.pi / 3.0)
                    u_offset = adsk.core.Vector3D.create(frame.u_dir[0], frame.u_dir[1], frame.u_dir[2])
                    v_offset = adsk.core.Vector3D.create(frame.v_dir[0], frame.v_dir[1], frame.v_dir[2])
                    u_offset.scaleBy(item.radius * math.cos(ang))
                    v_offset.scaleBy(item.radius * math.sin(ang))
                    pt = center_pt.copy()
                    pt.translateBy(u_offset)
                    pt.translateBy(v_offset)
                    coords.extend([pt.x, pt.y, pt.z])
                    indices.extend([k, (k + 1) % 6])

                cg_coords = adsk.fusion.CustomGraphicsCoordinates.create(coords)
                cg_lines = cg_group.addLines(cg_coords, indices, False)
                cg_lines.color = solid_color
                cg_lines.weight = 2.0
            else:
                # Default: Circle
                circle = adsk.core.Circle3D.createByCenter(center_pt, normal_vec, item.radius)
                cg_curve = cg_group.addCurve(circle)
                cg_curve.color = solid_color
                cg_curve.weight = 2.0

    except:
        cleanup_preview_graphics()


def command_input_changed(args: adsk.core.InputChangedEventArgs):
    """Fired whenever any dialog input changes. Updates pattern calculation & real-time preview."""
    try:
        inputs = args.inputs
        frame, items, status_msg = calculate_pattern_from_inputs(inputs)

        status_box: Optional[adsk.core.TextBoxCommandInput] = inputs.itemById('status_box')
        if status_box:
            status_box.text = f'<small style="color: #007acc;">{status_msg}</small>'

        update_preview_graphics(frame, items)
    except:
        futil.handle_error('command_input_changed', show_message_box=False)


def command_preview(args: adsk.core.CommandEventArgs):
    """Execute preview event."""
    try:
        inputs = args.command.commandInputs
        frame, items, status_msg = calculate_pattern_from_inputs(inputs)
        update_preview_graphics(frame, items)
    except:
        pass


def command_validate_input(args: adsk.core.ValidateInputsEventArgs):
    """Validate inputs."""
    try:
        inputs = args.inputs
        face_input: Optional[adsk.core.SelectionCommandInput] = inputs.itemById('face_selection')
        if face_input and face_input.selectionCount > 0:
            args.areInputsValid = True
        else:
            args.areInputsValid = False
    except:
        args.areInputsValid = False


def command_execute(args: adsk.core.CommandEventArgs):
    """Executes BRep feature creation upon clicking OK."""
    try:
        cleanup_preview_graphics()

        inputs = args.command.commandInputs
        face_input: Optional[adsk.core.SelectionCommandInput] = inputs.itemById('face_selection')
        if not face_input or face_input.selectionCount == 0:
            return

        selected_face: adsk.fusion.BRepFace = face_input.selection(0).entity
        frame, items, status_msg = calculate_pattern_from_inputs(inputs)
        if not items or not frame:
            if ui:
                ui.messageBox(f'No geometric pattern items generated.\n{status_msg}')
            return

        op_input: Optional[adsk.core.DropDownCommandInput] = inputs.itemById('operation')
        depth_input: Optional[adsk.core.ValueCommandInput] = inputs.itemById('extrude_depth')
        op_name = op_input.selectedItem.name.upper() if (op_input and op_input.selectedItem) else 'CUT'
        extrude_depth = depth_input.value if depth_input else 0.50

        comp = selected_face.body.parentComponent if (selected_face.body and selected_face.body.parentComponent) else app.activeProduct.rootComponent

        # 1. Create Sketch on the face
        sketches = comp.sketches
        sketch = sketches.add(selected_face)
        sketch.name = 'Geometric Pattern'

        sketch.isComputeDeferred = True

        sketch_circles = sketch.sketchCurves.sketchCircles
        sketch_lines = sketch.sketchCurves.sketchLines

        max_radius = 0.0
        for item in items:
            if item.radius > max_radius:
                max_radius = item.radius

            cx, cy, cz = item.world_center
            pt3d = adsk.core.Point3D.create(cx, cy, cz)
            sketch_pt = sketch.modelToSketchSpace(pt3d)

            if item.shape_type == 'box':
                half_s = item.radius
                p1 = adsk.core.Point3D.create(sketch_pt.x - half_s, sketch_pt.y - half_s, 0)
                p2 = adsk.core.Point3D.create(sketch_pt.x + half_s, sketch_pt.y - half_s, 0)
                p3 = adsk.core.Point3D.create(sketch_pt.x + half_s, sketch_pt.y + half_s, 0)
                p4 = adsk.core.Point3D.create(sketch_pt.x - half_s, sketch_pt.y + half_s, 0)
                sketch_lines.addByTwoPoints(p1, p2)
                sketch_lines.addByTwoPoints(p2, p3)
                sketch_lines.addByTwoPoints(p3, p4)
                sketch_lines.addByTwoPoints(p4, p1)
            elif item.shape_type == 'hexagon':
                pts = []
                for k in range(6):
                    ang = k * (math.pi / 3.0)
                    pts.append(adsk.core.Point3D.create(
                        sketch_pt.x + item.radius * math.cos(ang),
                        sketch_pt.y + item.radius * math.sin(ang),
                        0
                    ))
                for k in range(6):
                    sketch_lines.addByTwoPoints(pts[k], pts[(k + 1) % 6])
            else:
                center_2d = adsk.core.Point3D.create(sketch_pt.x, sketch_pt.y, 0)
                sketch_circles.addByCenterRadius(center_2d, item.radius)

        sketch.isComputeDeferred = False

        if 'SKETCH' in op_name:
            if ui:
                ui.messageBox(f'Created Geometric Pattern sketch with {len(items)} profiles.')
            return

        # 2. Select inner pattern profiles (excluding outer surrounding face)
        max_item_diam = max_radius * 2.5
        profiles = adsk.core.ObjectCollection.create()
        for prof in sketch.profiles:
            bb = prof.boundingBox
            pw = abs(bb.maxPoint.x - bb.minPoint.x)
            ph = abs(bb.maxPoint.y - bb.minPoint.y)
            if pw <= max_item_diam and ph <= max_item_diam:
                profiles.add(prof)

        if profiles.count == 0:
            # Fallback: add all closed profiles
            for prof in sketch.profiles:
                profiles.add(prof)

        if profiles.count == 0:
            if ui:
                ui.messageBox('No closed profiles found in sketch.')
            return

        # 3. Create Extrude Feature
        extrudes = comp.features.extrudeFeatures
        depth_val = adsk.core.ValueInput.createByReal(extrude_depth)

        if 'JOIN' in op_name:
            ext_input = extrudes.createInput(profiles, adsk.fusion.FeatureOperations.JoinFeatureOperation)
            ext_input.setDistanceExtent(False, depth_val)
        elif 'NEW' in op_name:
            ext_input = extrudes.createInput(profiles, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
            ext_input.setDistanceExtent(False, depth_val)
        else:  # Default: CUT
            depth_cut = adsk.core.ValueInput.createByReal(-abs(extrude_depth))
            ext_input = extrudes.createInput(profiles, adsk.fusion.FeatureOperations.CutFeatureOperation)
            ext_input.setDistanceExtent(False, depth_cut)
            if selected_face.body:
                ext_input.participantBodies = [selected_face.body]

        extrudes.add(ext_input)

    except:
        futil.handle_error('command_execute')


def command_destroy(args: adsk.core.CommandEventArgs):
    """Clean up handlers and graphics when command closes."""
    global local_handlers
    cleanup_preview_graphics()
    local_handlers = []
