
import bpy
from AnimAutomation import create_game_rig
import blender_auto_common


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


def register():
    """Registers this add-on to blender if user selected (called by blender)"""
    bpy.utils.register_class(ConstrainGameRig)
    bpy.utils.register_class(KeyBoneFromCurrent)
    bpy.utils.register_class(VIEW3D_PT_AnimHelperPanel)


def unregister():
    """Unregisters this add-on is user de-selected"""
    bpy.utils.unregister_class(VIEW3D_PT_AnimHelperPanel)
    bpy.utils.unregister_class(ConstrainGameRig)
    bpy.utils.unregister_class(KeyBoneFromCurrent)


if __name__ == '__main__':
    register()
