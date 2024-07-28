
import bpy
from AnimAutomation import create_game_rig
import blender_auto_common
import math


class ConstrainGameRig(bpy.types.Operator):
    """Constrains or unconstrain game rig to specified control rig so that control rig can animate character.

    Game rig is the exportable rig which contains deformation, joint target, etc bones that are used by the game engine,
    without the controls, mechanics, etc bones. The character mesh is parented and weighted to the game rig, so in
    order to animate the character using control rig, need to constrain the game rig to constrain rig."""

    bl_idname = "anim.constrain_game_rig"  # How to ref class from blender python
    bl_label = "Constrain Game Rig"  # Name in operator menu
    bl_options = {'REGISTER', 'UNDO'}  # Registers and enables undo

    ctrl_rig_name: bpy.props.StringProperty(name="Ctrl Rig Name", default="ctrl_rig",
        description="Name of Rig with controls to drive animations, this will be rig game rig will be constrained to")

    @classmethod
    def poll(cls, context):
        return context.mode == "POSE"

    def execute(self, context):
        game_rig_obj = blender_auto_common.find_object_in_mode("POSE", context=context)
        ctrl_rig_obj = bpy.data.objects[self.ctrl_rig_name]
        create_game_rig.CreateGameRig.constrain_game_rig(game_rig_obj, ctrl_rig_obj)
        return {'FINISHED'}

    def invoke(self, context, event):
        """Display a pop-up menu to let user set props (called by blender)"""
        return context.window_manager.invoke_props_dialog(self)


class KeyBoneFromCurrent(bpy.types.Operator):
    """Takes selected bone current viewport pose and keys it's location, rotation, and scale after all constraints,
    drivers, etc, applied. After this is run, user should turn off those constraints, drivers, etc"""

    bl_idname = "anim.key_bone_pose_from_current"  # How to ref class from blender python
    bl_label = "Key Bone Pose from Current"  # Name in operator menu
    bl_options = {'REGISTER', 'UNDO'}  # Registers and enables undo

    @classmethod
    def poll(cls, context):
        return context.mode == "POSE"

    def execute(self, context):
        for b in context.selected_pose_bones:
            bone_tm = b.bone.convert_local_to_pose(b.matrix, b.bone.matrix_local, invert=True)
            b.location = bone_tm.translation
            b.rotation_quaternion = bone_tm.to_quaternion()
            bpy.ops.anim.keyframe_insert(type="LocRotScale")
            print("Keyed Bone: " + str(b))
        return {'FINISHED'}


class CalcFootSpeed(bpy.types.Operator):
    """Calculates travel and speed in X and Y direction of feet IK when on the ground and displays to console

    USER NOTES:
        1) FPS, as taken from render settings, will be used to determine speed.
        2) Marker pref to foot bone name mapping must be set in a 'misc_armature_props.py' text data file in the
           blend file in a dict named 'foot_marker_prefs'
        3) The frames where each foot is on the ground must denoted by using pose markers (not timeline markers!),
           where the marker name should be [marker_pref][_Down/_Up] at the frame where that foot is down/up.
        4) If there is a target x or y speed for the feet add a 'y_speed' or 'x_speed' custom prop to the ACTION and
           this operator will output the needed additional foot displacement or time frame to the console"""

    bl_idname = "anim.calc_foot_speed"  # How to ref class from blender python
    bl_label = "Calc Foot Speed"  # Name in operator menu
    bl_options = {'REGISTER', 'UNDO'}  # Registers and enables undo

    ctrl_rig_name: bpy.props.CollectionProperty(type=bpy.props.StringProperty, name="Ctrl Rig Name")

    @staticmethod
    def get_up_down_feet_markers(act):
        """"Return dict of marker prefixes with feet bone names, dict of up markers, dict of down marker,
            with marker pref as keys"""
        up_markers = {}
        down_markers = {}
        marker_prefs = []
        for marker in act.pose_markers:
            pref = ""
            if "_Up" in marker.name:
                pref = marker.name.split('_Up', 1)[0]
                if pref and pref not in up_markers.keys():
                    up_markers[pref] = marker
            elif "_Down" in marker.name:
                pref = marker.name.split('_Down', 1)[0]
                if pref and pref not in down_markers.keys():
                    down_markers[pref] = marker
            if pref not in marker_prefs:
                marker_prefs.append(pref)
        good_marker_prefs = {}
        if bpy.context.blend_data.texts.find('misc_armature_props.py') < 0:
            raise Exception("Could not get 'misc_armature_props' text file in current blend file")
        arm_props = bpy.context.blend_data.texts['misc_armature_props.py'].as_module()
        for marker_pref in marker_prefs:
            if marker_pref in up_markers.keys() and marker_pref in down_markers.keys() \
                    and marker_pref in arm_props.foot_marker_prefs.keys():
                good_marker_prefs[marker_pref] = arm_props.foot_marker_prefs[marker_pref]
        if not good_marker_prefs:
            raise Exception("Could not find good up/down markers for act: " + act.name)
        return good_marker_prefs, up_markers, down_markers

    @staticmethod
    def calc_foot_speed(act):
        """Return dictionary containing speeds, distances, and times of feet bones"""
        fps = bpy.context.scene.render.fps
        if act is None:
            raise Exception("No active action")
        marker_prefs, up_markers, down_markers = CalcFootSpeed.get_up_down_feet_markers(act)
        out = {}
        for pref, ft in marker_prefs.items():
            out[ft] = {'x_delta': None, 'y_delta': None, 't_delta': None, 'x_speed': None, 'y_speed': None,
                       'speed_mag': None}
            fc_x = act.fcurves.find('pose.bones["%s"].location' % ft, index=0)
            fc_y = act.fcurves.find('pose.bones["%s"].location' % ft, index=1)
            down_frame = down_markers[pref].frame
            up_frame = up_markers[pref].frame
            x_kf_up = blender_auto_common.get_fcurve_keyframe_at_frame(up_frame, fc_x)[1]
            x_kf_down = blender_auto_common.get_fcurve_keyframe_at_frame(down_frame, fc_x)[1]
            y_kf_up = blender_auto_common.get_fcurve_keyframe_at_frame(up_frame, fc_y)[1]
            y_kf_down = blender_auto_common.get_fcurve_keyframe_at_frame(down_frame, fc_y)[1]
            if x_kf_up is None or x_kf_down is None or y_kf_up is None or y_kf_down is None:
                raise Exception("No key frames on fcurves at the up/down marker locations")
            out[ft]['x_delta'] = x_kf_up.co[1] - x_kf_down.co[1]
            out[ft]['y_delta'] = y_kf_up.co[1] - y_kf_down.co[1]
            out[ft]['t_delta'] = float(up_frame) - float(down_frame)
            if down_frame > up_frame:
                out[ft]['t_delta'] += act.frame_range[1] - act.frame_range[0]  # plus b/c last frame needs to wrap to first
            out[ft]['t_delta'] *= 1. / float(fps)
            out[ft]['x_speed'] = out[ft]['x_delta'] / out[ft]['t_delta']
            out[ft]['y_speed'] = out[ft]['y_delta'] / out[ft]['t_delta']
            out[ft]['speed_mag'] = math.sqrt(out[ft]['x_speed'] ** 2 + out[ft]['y_speed'] ** 2)
        return out

    @classmethod
    def poll(cls, context):
        return context.mode == "POSE"

    def execute(self, context):
        rig_obj = blender_auto_common.find_object_in_mode('POSE')  # Get current pose mode rig0
        act = rig_obj.animation_data.action
        feet_speed = self.calc_foot_speed(act)
        print("\n\n")
        print(act.name + ":")
        for ft in feet_speed.keys():
            if feet_speed[ft]['speed_mag'] is None:
                continue
            print(ft + "    Speed: [ %.7f  %.7f ]  ->  %.3f" % (feet_speed[ft]['x_speed'],
                                                      feet_speed[ft]['y_speed'],
                                                      feet_speed[ft]['speed_mag']))
            print("        Delta: [ X:%.7f  Y:%.7f    t:%.7f]" % (feet_speed[ft]['x_delta'],
                                                      feet_speed[ft]['y_delta'],
                                                      feet_speed[ft]['t_delta']))
            delta_dist = None
            delta_time = None
            # note foot delta and foot speed is opposite of tgt char speed
            if act.get('x_speed') is not None:
                delta_dist = - act['x_speed'] * feet_speed[ft]['t_delta'] - feet_speed[ft]['x_delta']
                delta_time = - feet_speed[ft]['x_delta'] / act['x_speed'] - feet_speed[ft]['t_delta']
            if act.get('y_speed') is not None:
                delta_dist = - act['y_speed'] * feet_speed[ft]['t_delta'] - feet_speed[ft]['y_delta']
                delta_time = - feet_speed[ft]['y_delta'] / act['y_speed'] - feet_speed[ft]['t_delta']
            if delta_dist is not None and delta_time is not None:
                print("        Delta Dist Needed: %.7f" % delta_dist)
                print("        Delta Time Needed: %.7f" % delta_time)
        return {'FINISHED'}


class VIEW3D_PT_AnimHelperPanel(bpy.types.Panel):
    """Displays Anim Helpers Operators in N-Panel Animation Tab in Pose mode"""

    bl_label = "Anim Helpers"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Animation"

    @classmethod
    def poll(cls, context):
        if context.mode != 'POSE':
            return False
        return True

    def draw(self, _):
        layout = self.layout
        sub = layout.column(align=True)
        layout.operator(ConstrainGameRig.bl_idname, text=ConstrainGameRig.bl_label)
        layout.operator(KeyBoneFromCurrent.bl_idname, text=KeyBoneFromCurrent.bl_label)
        layout.operator(CalcFootSpeed.bl_idname, text=CalcFootSpeed.bl_label)


def register():
    """Registers this add-on to blender if user selected (called by blender)"""
    bpy.utils.register_class(ConstrainGameRig)
    bpy.utils.register_class(KeyBoneFromCurrent)
    bpy.utils.register_class(CalcFootSpeed)
    bpy.utils.register_class(VIEW3D_PT_AnimHelperPanel)


def unregister():
    """Unregisters this add-on is user de-selected"""
    bpy.utils.unregister_class(VIEW3D_PT_AnimHelperPanel)
    bpy.utils.unregister_class(ConstrainGameRig)
    bpy.utils.unregister_class(KeyBoneFromCurrent)
    bpy.utils.unregister_class(CalcFootSpeed)


if __name__ == '__main__':
    register()
