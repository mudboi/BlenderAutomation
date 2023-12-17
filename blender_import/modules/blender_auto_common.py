import bpy
import ast
import mathutils
from collections import OrderedDict


game_to_ctrl_constraint_pref = "CtrlRigConst_"
anim_retgt_copy_rig_constraint_pref = "CtrlRigCopyConst_"


class RigifyLimbIKBakeSettings:
    def __init__(self, prop_bone='', fk_bones='[]', ik_bones='[]', ctrl_bones='[]', tail_bones='[]', extra_ctrls='[]'):
        self.prop_bone = prop_bone
        self.fk_bones = fk_bones
        self.ik_bones = ik_bones
        self.ctrl_bones = ctrl_bones
        self.tail_bones = tail_bones
        self.extra_ctrls = extra_ctrls

    def get_bone_flat_list(self):
        out_list = []
        out_list += [self.prop_bone]
        out_list += self.parse_string_list(self.fk_bones)
        out_list += self.parse_string_list(self.ik_bones)
        out_list += self.parse_string_list(self.ctrl_bones)
        out_list += self.parse_string_list(self.tail_bones)
        out_list += self.parse_string_list(self.extra_ctrls)
        return out_list

    @staticmethod
    def parse_string_list(parse_str):
        try:
            return ast.literal_eval(parse_str)
        except SyntaxError as se:
            raise Exception("Could not parse limb IK bake setting bone list") from se


def switch_to_mode(obj, mode, context=None):
    """Switches obj to mode given by 'mode'.

    NOTE: Will deselect any currently selected and/or activated objects and leave
    object selected and activated"""
    obj.select_set(True)  # Need to select AND activate obj to switch modes
    if context:
        context.view_layer.objects.active = obj
    else:
        bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode=mode)


def find_object_in_mode(mode, raise_if_missing=True, context=None):
    """Find an object that is currently in a mode given by 'mode'.

        If 'raise_if_missing' set to true, will raise exception if not find, otherwise will return
        a None object. If multiple objects in mode, will return the first one found (I believe multiple
        objects can only be in 'OBJECT' mode, the other modes can only have a single object."""
    mode_obj = None
    if not context:
        context = bpy.context
    for obj in context.scene.objects:
        if obj.mode == mode:
            mode_obj = obj
            break
    if mode_obj is None and raise_if_missing:
        raise Exception("Could not find any object in " + mode + " mode")
    return mode_obj


def get_export_armature():
    """ Get first armature that is in a collection called 'Export' or None if one not found.

    This is useful for getting the send2ue armature that contains all the unreal export animations"""
    try:
        export_col = bpy.data.collections['Export']
    except KeyError:
        return None
    for obj in export_col.objects:
        if obj.type == 'ARMATURE':
            return obj.data
    return None


def move_obj_to_coll(context, obj, coll_name, raise_if_err=False):
    tgt_coll = context.scene.collection.children.get("Extra")
    if not tgt_coll:
        if raise_if_err:
            raise Exception("Could not move obj: " + obj.name + ", no collection exists for: " + coll_name)
        return
    for coll in obj.users_collection:
        coll.objects.unlink(obj)
    tgt_coll.objects.link(obj)


def push_action_to_nla(rig_obj):
    """Push 'rig_obj's active action to NLA"""
    act = rig_obj.animation_data.action  # Get current action
    track = rig_obj.animation_data.nla_tracks.new()  # create new NLA track and push action to it
    track.strips.new(act.name, int(act.frame_range[0]), act)
    rig_obj.animation_data.action = None  # Unlink the action as active action


def toggle_rig_constraints(enable, constrain_rig, pref_identifier, bone_names=None):
    """Toggle constraints id'ed by pref_identifier for all bones in rig, or just bones in bone_names if specified

    pref_identifier for example could be game_to_ctrl_constraint_pref, and this function will go through all
    constraints in bones and enable or disable game rig to control rig loc/rot constraints. This method does not
    add or remove any constraints, and will not disable/enable any other constraints besides the ones identified
    by pref_identifier."""
    for bone in constrain_rig.pose.bones:
        if bone_names:
            if bone.name not in bone_names:
                continue
        for cnst in bone.constraints:
            if cnst.name[:len(pref_identifier)] == pref_identifier:
                cnst.enabled = enable


def traverse_bone_heirarchy(bn, operator, method):
    """Recursively tranverse a bone heirarchy and perform operation on each bone.

        Should pass in root bones as 'bn', function will recursively call itself on
        all child bones. 'operator' is any object that has a method named 'method' to
        call on every bone recursively"""
    getattr(operator, method)(bn)
    for ch in bn.children:
        traverse_bone_heirarchy(ch, operator, method)
