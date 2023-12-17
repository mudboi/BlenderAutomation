import bpy
from AnimAutomation import bake_all_to_rig, create_game_rig, retarget_anim_to_rigify, rig_helpers


modules = (bake_all_to_rig, create_game_rig, retarget_anim_to_rigify, rig_helpers)


bl_info = {
    "name": "Animation Automation",
    "author": "Inderbir Sidhu",
    "version": (1, 0, 0),
    "blender": (2, 93, 0),
    "description": "Collection of custom functionality for automating blender animation",
    "warning": "",
    "category": "Animation",
}


def pose_menu_func(self, context):
    self.layout.separator()
    for m in modules:
        if hasattr(m, 'pose_menu_func'):
            getattr(m, 'pose_menu_func')(self, context)


def armature_add_menu_func(self, context):
    self.layout.separator()
    for m in modules:
        if hasattr(m, 'armature_add_menu_func'):
            getattr(m, 'armature_add_menu_func')(self, context)


def register():
    for m in modules:
        m.register()
    bpy.types.VIEW3D_MT_pose.append(pose_menu_func)
    bpy.types.VIEW3D_MT_armature_add.append(armature_add_menu_func)


def unregister():
    bpy.types.VIEW3D_MT_pose.remove(pose_menu_func)
    bpy.types.VIEW3D_MT_armature_add.remove(armature_add_menu_func)
    for m in modules:
        m.unregister()


if __name__ == "__main__":
    register()
