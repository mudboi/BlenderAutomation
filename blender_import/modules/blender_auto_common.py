import bpy
import ast
import mathutils
from collections import OrderedDict


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
    bpy.ops.object.select_all(action='DESELECT')
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


def push_action_to_nla(rig_obj):
    """Push 'rig_obj's active action to NLA"""
    act = rig_obj.animation_data.action  # Get current action
    track = rig_obj.animation_data.nla_tracks.new()  # create new NLA track and push action to it
    track.strips.new(act.name, int(act.frame_range[0]), act)
    rig_obj.animation_data.action = None  # Unlink the action as active action


def toggle_constrain_bones_rig_to_rig(constrain, src_rig, constrain_rig, bones, verbose=True):
    """Constrain or unconstrain the bones specified by bones in constrain_rig to corresponding bones in src_rig

    Note: corresponding bones have to be named identical in both rigs. Removes all other bone constraints from
    bones not used for constraining them"""
    for bone_name in bones:
        cnst_bone_ind = constrain_rig.pose.bones.find(bone_name)
        src_bone_ind = src_rig.pose.bones.find(bone_name)
        if cnst_bone_ind < 0 or src_bone_ind < 0:
            if verbose:
                print("Could not find bone: " + bone_name + " in  either constrain rig or source rig")
            continue
        if verbose:
            toggle = "ON" if constrain else "OFF"
            print("Toggling constraints " + toggle + " for: " + bone_name)
        cnst_bone = constrain_rig.pose.bones[cnst_bone_ind]
        src_bone = src_rig.pose.bones[src_bone_ind]
        for cnst in cnst_bone.constraints:
            if verbose:
                print("    Removing constraint: " + cnst.type + ": " + cnst.name)
            cnst_bone.constraints.remove(cnst)
        loc = cnst_bone.constraints.new(type="COPY_LOCATION")
        loc.target = src_rig
        loc.subtarget = src_bone.name
        loc.enabled = constrain
        rot = cnst_bone.constraints.new(type="COPY_ROTATION")
        rot.target = src_rig
        rot.subtarget = src_bone.name
        rot.enabled = constrain


def traverse_bone_heirarchy(bn, operator, method):
    """Recursively tranverse a bone heirarchy and perform operation on each bone.

        Should pass in root bones as 'bn', function will recursively call itself on
        all child bones. 'operator' is any object that has a method named 'method' to
        call on every bone recursively"""
    getattr(operator, method)(bn)
    for ch in bn.children:
        traverse_bone_heirarchy(ch, operator, method)
