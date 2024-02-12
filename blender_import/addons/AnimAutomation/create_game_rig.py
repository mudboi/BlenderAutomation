
import bpy
import mathutils
from collections import OrderedDict
import blender_auto_common


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


class CreateGameRig(bpy.types.Operator):
    """Creates a game ready rig from a Rigify rig using rigify ctrl rig DEF bones and any bones user tags
    with custom bone property KEEP_GAME_RIG with game rig name as the prop value.

    USER NOTES:
      1) Game Rig should not have the same exact bone names as ctrl_rig, since if in blender you apply an
         action meant for the game rig onto the ctrl rig, the ctrl rig will get messed up, since ctrl rig
         has same named bones (DEF-) bones that are not meant to be keyframed. This operator will make sure
         no bone names match with ctrl rig by either:
            a) using KEEP_GAME_RIG bone prop value (can't match ctrl rig bone name)
            b) removing "DEF-" prefix
      2) If KEEP_GAME_RIG used on a bone, the game rig bone will have an identical KEEP_GAME_RIG bone property
         that has the ctrl rig bone name, this way the ctrl rig bone prop and game rig bone prop has maps to
         their respective bone in the other rig
      3) Run operator defined below, by going to object mode, click Add Menu -> Armature ->
         Game Rig
      4) Fix game rig heirarchy (if desired, doesn't make a big difference to blender) afterwards
      5) Parent the game rig to character mesh afterwards"""

    bl_idname = "armature.create_game_rig"  # How to ref class from blender python
    bl_label = "Game Rig"  # Name in operator menu
    bl_options = {'REGISTER', 'UNDO'}  # Registers and enables undo

    #  Below properties control how the operator performs
    ctrl_rig_name: bpy.props.StringProperty(name="Rigify Rig Name", default="ctrl_rig",
        description="Rigify Rig to create Game Rig from")

    game_rig_name: bpy.props.StringProperty(name="Game Rig Name", default="game_rig",
        description="Name for the created Game Rig")

    @staticmethod
    def ctrl_to_game_rig_bone_name(ctrl_rig_bname, keep_gr_prop):
        if keep_gr_prop:
            return keep_gr_prop
        if "DEF-" in ctrl_rig_bname:
            return "def-" + ctrl_rig_bname.split("DEF-", 1)[1]
        return None

    @staticmethod
    def game_to_ctrl_rig_bone_name(game_rig_bname, keep_gr_prop):
        if keep_gr_prop:
            return keep_gr_prop
        if "def-" in game_rig_bname:
            return "DEF-" + game_rig_bname.split("def-", 1)[1]
        return None

    @staticmethod
    def constrain_game_rig(game_rig_obj, ctrl_rig_obj):
        print(" Applying Game Rig Constraints ....")
        for bone in game_rig_obj.pose.bones:  # Pose Bones NOT Edit Bones
            print("Constraining: " + bone.name)
            keep_game_rig = bone.get("KEEP_GAME_RIG")  # note some bones have a pref attached
            cr_name = CreateGameRig.game_to_ctrl_rig_bone_name(bone.name, keep_game_rig)
            loc_const_name = blender_auto_common.game_to_ctrl_constraint_pref + "Loc"
            rot_const_name = blender_auto_common.game_to_ctrl_constraint_pref + "Rot"
            loc_constrained = False
            rot_constrained = False
            for con in bone.constraints:  # remove all current constraints
                if not loc_constrained and con.name == loc_const_name:
                    print("    Reenabling Constraint: " + con.name)
                    con.enabled = True
                    loc_constrained = True
                elif not rot_constrained and con.name == rot_const_name:
                    print("    Reenabling Constraint: " + con.name)
                    con.enabled = True
                    rot_constrained = True
                else:
                    print("    Removing Constraint: " + con.type + ": " + con.name)
                    bone.constraints.remove(con)
            if not loc_constrained:
                print("    Adding Constraint: " + loc_const_name)
                loc = bone.constraints.new(type="COPY_LOCATION")
                loc.name = loc_const_name
                loc.target = ctrl_rig_obj
                loc.subtarget = cr_name
            if not rot_constrained:
                print("    Adding Constraint: " + rot_const_name)
                rot = bone.constraints.new(type="COPY_ROTATION")
                rot.name = rot_const_name
                rot.target = ctrl_rig_obj
                rot.subtarget = cr_name
        print("Finished applying game rig constraints")

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
        if context.blend_data.collections.find('Export') < 0:  # Check if 'Export' Collection does not exists
            exp_col = context.blend_data.collections.new('Export')  # Create and link to current scene if not
            context.scene.collection.children.link(exp_col)
        else:
            exp_col = context.blend_data.collections['Export']  # Grab ref if it does
        if context.blend_data.collections['Export'].objects.find(self.game_rig_name):  # Check if game rig in 'Rig'
            exp_col.objects.link(game_rig_obj)  # Link to collection if not

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
                blender_auto_common.traverse_bone_heirarchy(bone, bone_copier, 'copy_edit_bone_data')

        # Select game rig and make active, then switch to edit mode, then create bones from
        #     previously copied ctrl rig edit bone data
        bpy.ops.object.mode_set(mode='OBJECT')  # MODE SWTICH~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        blender_auto_common.switch_to_mode(game_rig_obj, 'EDIT', context=context)  # MODE SWTICH~~~
        cr_to_gr_names = {}
        custom_name_gr_to_cr = {}
        keep_bones = []
        for (cb_name, cb_attrs) in bone_copier.ctrl_rig_attrs.items():
            # Iter over all ctrl_rig edit bone attribute data copied
            keep_game_rig = ctrl_rig_obj.pose.bones[cb_name].get("KEEP_GAME_RIG")  # custom prop to keep bone in gr
            gr_name = self.ctrl_to_game_rig_bone_name(cb_name, keep_game_rig)
            if gr_name:
                keep_bones.append(gr_name)
                if ctrl_rig_obj.pose.bones.find(gr_name) != -1:
                    raise Exception("Can't have identical game rig and ctrl rig bone name: " + gr_name)
            else:
                gr_name = cb_name
            cr_to_gr_names[cb_name] = gr_name
            if keep_game_rig:
                custom_name_gr_to_cr[gr_name] = cb_name
            if game_rig_arm.edit_bones.find(gr_name) < 0:
                # Check if game_rig edit bone by the same name does not exist and create if not
                game_bone = game_rig_arm.edit_bones.new(gr_name)
            else:  # if already exists grab a ref
                game_bone = game_rig_arm.edit_bones[gr_name]
            # Even if game_rig edit bone already existed, ctrl_rig edit bone attribute data
            #     might have changed since script previously run, so overwriting all values
            game_bone.bbone_segments = 1
            for (attr, val) in cb_attrs.items():
                if attr == 'parent' and val is not None:  # if edit bone needs to be parented
                    # Need to find game_rig edit bone with name corresponding to ctrl_rig edit
                    #     bone's parent and use the ref to that bone to parent this bone
                    gr_parent_name = cr_to_gr_names[val]
                    parent_bone_ind = game_rig_arm.edit_bones.find(gr_parent_name)
                    game_bone.parent = game_rig_arm.edit_bones[parent_bone_ind]
                else:
                    setattr(game_bone, attr, val)

        # In Edit Mode, select all bones that are not Rigify Deform bones (prefixed with "DEF-")
        #     or are DEF- bones that don't exist in the ctrl_rig anymore and delete them
        bpy.ops.armature.select_all(action='DESELECT')
        for bone in game_rig_arm.edit_bones:
            if bone.name not in keep_bones:
                bone.select = True
        bpy.ops.armature.delete()
        # Need to exit out of edit mode to save edit bones
        bpy.ops.object.mode_set(mode='OBJECT')  # MODE SWITCH ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        # Add "KEEP_GAME_RIG custom prop to game_rig bones
        for gr_name, cr_name in custom_name_gr_to_cr.items():
            game_rig_obj.pose.bones[gr_name]["KEEP_GAME_RIG"] = cr_name

        self.constrain_game_rig(game_rig_obj, ctrl_rig_obj)
        return {'FINISHED'}

    def invoke(self, context, event):
        """Display a pop-up menu to let user set props (called by blender)"""
        return context.window_manager.invoke_props_dialog(self)


def armature_add_menu_func(self, _):
    """Draws menu (passed to blender)"""
    self.layout.operator(CreateGameRig.bl_idname)


def register():
    """Registers this add-on to blender if user selected (called by blender)"""
    bpy.utils.register_class(CreateGameRig)


def unregister():
    """Unregisters this add-on is user de-selected"""
    bpy.utils.unregister_class(CreateGameRig)


if __name__ == '__main__':
    register()
