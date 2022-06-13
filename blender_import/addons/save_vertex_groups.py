# USER NOTES:



bl_info = {
    "name": "Save Vertex Groups",
    "author": "Inderbir Sidhu",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Add > Armature > Game Rig",
    "description": "Create a game-ready rig from a Rigify rig",
    "warning": "",
    "category": "Rigging",
}


import bpy
import mathutils
from collections import OrderedDict
import blender_auto_common


# HELPER FUNCTIONS AND CLASSES ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def traverse_bone_heirarchy(bn, operator, method):
    """Recursively tranverse a bone heirarchy and perform operation on each bone.

        Should pass in root bones as 'bn', function will recursively call itself on
        all child bones. 'operator' is any object that has a method named 'method' to
        call on every bone recursively"""
    getattr(operator, method)(bn)
    for ch in bn.children:
        traverse_bone_heirarchy(ch, operator, method)


class EditBoneCopier:
    """Class to copy edit bones attributes.

    Attributes to copy are listed in the class variable 'attrs_to_copy'. Will fill
    out an OrderedDict, 'ctrl_rig_attrs', with all attribute data from all bones passed to
    'copy_edit_bone_data()' method, keys will be bone names, vals will be a dict with
    attribute name: attribute value"""
    attrs_to_copy = ['envelope_distance', 'envelope_weight', 'head', 'head_radius',
                     'inherit_scale', 'tail', 'tail_radius', 'use_connect', 'roll',
                     'use_deform', 'use_endroll_as_inroll', 'use_envelope_multiply',
                     'use_inherit_rotation', 'use_local_location', 'use_relative_parent']

    def __init__(self):
        self.ctrl_rig_attrs = OrderedDict()

    def copy_edit_bone_data(self, ctrl_bone):
        """Copy edit bone data from 'ctrl_bone' and stores in 'ctrl_rig_attrs'.

        'ctrl_bone' MUST be an edit bone, and passed in whatever order desired, this
        class will keep track of that order through the use of an OrderedDict to
        store the copied data.
        """
        self.ctrl_rig_attrs[ctrl_bone.name] = {}
        if ctrl_bone.parent:  # Check if bone has parent and get name str
            self.ctrl_rig_attrs[ctrl_bone.name]['parent'] = ctrl_bone.parent.name
        else:
            self.ctrl_rig_attrs[ctrl_bone.name]['parent'] = None
        for at in self.attrs_to_copy:  # iter over attr_to_copy and copy values
            if type(getattr(ctrl_bone, at)) is mathutils.Vector:
                # Blender deallocates memory for vectors and matrices when leaving edit
                #     mode, so need to make a copy to store
                self.ctrl_rig_attrs[ctrl_bone.name][at] = getattr(ctrl_bone, at).copy()
            else:
                self.ctrl_rig_attrs[ctrl_bone.name][at] = getattr(ctrl_bone, at)


# MAIN CLASSES ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


class CreateGameRig(bpy.types.Operator):
    """Creates a game ready rig from a Rigify rig.
    NOTE: To keep certain non-deform bones, in POSE MODE tag them with the custom property:
    KEEP_GAME_RIG"""

    bl_idname = "armature.create_game_rig"  # How to ref class from blender python
    bl_label = "Game Rig"  # Name in operator menu
    bl_options = {'REGISTER', 'UNDO'}  # Registers and enables undo

    #  Below properties control how the operator performs
    ctrl_rig_name: bpy.props.StringProperty(name="Rigify Rig Name", default="ctrl_rig",
                                            description="Rigify Rig to create Game Rig from")
    game_rig_name: bpy.props.StringProperty(name="Game Rig Name", default="game_rig",
                                            description="Name for the created Game Rig")

    def execute(self, context):
        """Take control rig and creates a game rig (called by Blender when operator invoked by user).

        A game ready rig is one that takes deform bones, plus any other user selected bones, from
        a Rigify control rig (rig actually used to animate) and copies them into a seperate rig. This
        rig is constrained to move with the control rig, so it is able to be animated, but since it
        just has the deform bones, it is much easier to export to game engine."""

        # Get ref to ctrl and game rigs, create game rig if it doesn't exist, note there are two
        #     things needed the blender object and the blender armature
        if context.scene.objects.find(self.ctrl_rig_name) < 0:  # Check if ctrl_rig exists
            raise Exception("Could not find control rig: " + self.ctrl_rig_name)
        ctrl_rig_obj = context.scene.objects[self.ctrl_rig_name]
        ctrl_rig_arm = ctrl_rig_obj.data
        if context.scene.objects.find(self.game_rig_name) < 0:  # Check if game rig does not exist
            game_rig_arm = context.blend_data.armatures.new(self.game_rig_name)  # create if not
            game_rig_obj = context.blend_data.objects.new(self.game_rig_name, game_rig_arm)
        else:
            game_rig_obj = context.scene.objects[self.game_rig_name]  # get ref if it does
            game_rig_arm = game_rig_obj.data
        if context.blend_data.collections.find('Rig') < 0:  # Check if 'Rig' Collection does not exists
            rig_col = context.blend_data.collections.new('Rig')  # Create and link to current scene if not
            context.scene.collection.children.link(rig_col)
        else:
            rig_col = context.blend_data.collections['Rig']  # Grab ref if it does
        if context.blend_data.collections['Rig'].objects.find(self.game_rig_name):  # Check if game rig in 'Rig'
            rig_col.objects.link(game_rig_obj)  # Link to collection if not

        # Select ctrl rig and make active -> switch it to edit mode -> itterate through
        #     all root-level bones -> recursively itterate through children of those root-level bones
        #     to get all ctrl rig edit bone data to copy to the game rig. Note, recursive itteration
        #     is necessary for parenting bones in the game rig, since the order of grabbing ctrl rig
        #     edit bone data is kept and used later when creating game rig edit bones (need to
        #     create parent bones before children to parent the children)
        #  TO DO: Make this able to run from any mode
        blender_auto_common.switch_to_mode(ctrl_rig_obj, 'EDIT', context=context)  # MODE SWTICH~~~
        bone_copier = EditBoneCopier()
        for bone in ctrl_rig_arm.edit_bones:  # Important to pass edit_bones
            if bone.parent is None:  # Check if root-level bone
                traverse_bone_heirarchy(bone, bone_copier, 'copy_edit_bone_data')

        # Select game rig and make active, then switch to edit mode, then create bones from
        #     previously copied ctrl rig edit bone data
        bpy.ops.object.mode_set(mode='OBJECT')  # MODE SWTICH~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        blender_auto_common.switch_to_mode(game_rig_obj, 'EDIT', context=context)  # MODE SWTICH~~~
        for (cb_name, cb_attrs) in bone_copier.ctrl_rig_attrs.items():
            # Iter over all ctrl_rig edit bone attribute data copied
            if game_rig_arm.edit_bones.find(cb_name) < 0:
                # Check if game_rig edit bone by the same name does not exist and create if not
                game_bone = game_rig_arm.edit_bones.new(cb_name)
            else:  # if already exists grab a ref
                game_bone = game_rig_arm.edit_bones[cb_name]
            # Even if game_rig edit bone already existed, ctrl_rig edit bone attribute data
            #     might have changed since script previously run, so overwriting all values
            game_bone.bbone_segments = 1
            for (attr, val) in cb_attrs.items():
                if attr == 'parent' and val is not None:  # if edit bone needs to be parented
                    # Need to find game_rig edit bone with name identical to ctrl_rig edit
                    #     bone's parent and use the ref to that bone to parent this bone
                    parent_bone_ind = game_rig_arm.edit_bones.find(val)
                    game_bone.parent = game_rig_arm.edit_bones[parent_bone_ind]
                else:
                    setattr(game_bone, attr, val)

        # In Edit Mode, select all bones that are not Rigify Deform bones (prefixed with "DEF-")
        #     or are DEF- bones that don't exist in the ctrl_rig anymore and delete them
        bpy.ops.armature.select_all(action='DESELECT')
        keep_in_game_rig = {}  # [ctrl_rig_name]: game_rig_pref
        for bone in game_rig_arm.edit_bones:
            if ctrl_rig_arm.bones.find(bone.name) < 0:
                # Checks if ctrl_rig has a corresponding bone (with same name), if not it means
                #     the bone was deleted from the ctrl_rig since script previously ran and
                #     need to delete it from game rig as well
                bone.select = True
            elif bone.name[:4] != "DEF-":
                # custom props can either be None (doesn't exist), empty string/num, or string/num
                keep = ctrl_rig_obj.pose.bones[bone.name].get("KEEP_GAME_RIG")
                if keep is None:
                    bone.select = True
                else:
                    keep_in_game_rig[bone.name] = keep
                    if keep:
                        bone.name = keep + bone.name
        bpy.ops.armature.delete()
        # Need to exit out of edit mode to save edit bones
        bpy.ops.object.mode_set(mode='OBJECT')  # MODE SWITCH ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        # Add "KEEP_GAME_RIG custom prop to game_rig bones
        for bone_name, pref in keep_in_game_rig.items():
            game_rig_obj.pose.bones[pref + bone_name]["KEEP_GAME_RIG"] = pref

        # Finally constrain  all bones, if not already constrained to the ctrl_rig for animating
        for bone in game_rig_obj.pose.bones:  # Pose Bones NOT Edit Bones
            loc_constrained = False
            rot_constrained = False
            game_rig_pref = bone.get("KEEP_GAME_RIG")
            for con in bone.constraints:  # iter over all Pose Bones to check const exists
                if con.type == "COPY_LOCATION" and con.subtarget == bone.name:
                    loc_constrained = True
                elif con.type == "COPY_ROTATION" and con.subtarget == bone.name:
                    rot_constrained = True
            if not loc_constrained:
                loc = bone.constraints.new(type="COPY_LOCATION")
                loc.target = ctrl_rig_obj
                if game_rig_pref is not None:
                    loc.subtarget = bone.name[len(game_rig_pref):]
                else:
                    loc.subtarget = bone.name
            if not rot_constrained:
                rot = bone.constraints.new(type="COPY_ROTATION")
                rot.target = ctrl_rig_obj
                if game_rig_pref is not None:
                    rot.subtarget = bone.name[len(game_rig_pref):]
                else:
                    rot.subtarget = bone.name
        return {'FINISHED'}

    def invoke(self, context, event):
        """Display a pop-up menu to let user set props (called by blender)"""
        return context.window_manager.invoke_props_dialog(self)


def menu_func(self, context):
    """Draws menu (passed to blender)"""
    self.layout.operator(CreateGameRig.bl_idname)


def register():
    """Registers this add-on to blender if user selected (called by blender)"""
    bpy.utils.register_class(CreateGameRig)
    bpy.types.VIEW3D_MT_armature_add.append(menu_func)


def unregister():
    """Unregisters this add-on is user de-selected"""
    bpy.types.VIEW3D_MT_armature_add.remove(menu_func)
    bpy.utils.unregister_class(CreateGameRig)


if __name__ == '__main__':
    register()
