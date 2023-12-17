
import bpy
import blender_auto_common


class ConstrainGameRig(bpy.types.Operator):
    """"""

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
        print(" APPLYING GAME RIG CONSTRAINTS ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        for bone in game_rig_obj.pose.bones:  # Pose Bones NOT Edit Bones
            print("Constraining: " + bone.name)
            loc_constrained = False
            rot_constrained = False
            game_rig_pref = bone.get("KEEP_GAME_RIG")
            for con in bone.constraints:  # remove all current constraints
                print("    Removing Constraint: " + con.type + ": " + con.name)
                bone.constraints.remove(con)
            loc = bone.constraints.new(type="COPY_LOCATION")
            loc.target = ctrl_rig_obj
            if game_rig_pref is not None:
                loc.subtarget = bone.name[len(game_rig_pref):]
            else:
                loc.subtarget = bone.name
            rot = bone.constraints.new(type="COPY_ROTATION")
            rot.target = ctrl_rig_obj
            if game_rig_pref is not None:
                rot.subtarget = bone.name[len(game_rig_pref):]
            else:
                rot.subtarget = bone.name
        print(" FINISHED APPLYING GAME RIG CONSTRAINTS ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        return {'FINISHED'}

    def invoke(self, context, event):
        """Display a pop-up menu to let user set props (called by blender)"""
        return context.window_manager.invoke_props_dialog(self)


class VIEW3D_PT_RigHelperPanel(bpy.types.Panel):
    """Displays Rig Helpers Operators in N-Panel Animation Tab in Pose mode"""

    bl_label = "Rig Helpers"
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


def register():
    """Registers this add-on to blender if user selected (called by blender)"""
    bpy.utils.register_class(ConstrainGameRig)
    bpy.utils.register_class(VIEW3D_PT_RigHelperPanel)


def unregister():
    """Unregisters this add-on is user de-selected"""
    bpy.utils.unregister_class(VIEW3D_PT_RigHelperPanel)
    bpy.utils.unregister_class(ConstrainGameRig)


if __name__ == '__main__':
    register()
