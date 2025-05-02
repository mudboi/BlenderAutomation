import bpy
import ast
import mathutils
import math
from collections import OrderedDict


game_to_ctrl_constraint_pref = "CtrlRigConst_"
anim_retgt_intermediate_rig_constraint_pref = "CtrlRigIntermedConst_"


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
    bpy.ops.object.mode_set(mode='OBJECT')  # first switch to obj mode
    bpy.ops.object.select_all(action='DESELECT')  # so we can deselect all
    obj.select_set(True)  # Need to select AND activate obj to switch modes
    if context:
        context.view_layer.objects.active = obj
    else:
        bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode=mode)

def get_first_screen_area_of_type(screen_type, context, make_sure_only=False):
    return_area = None
    counter = 0
    for area in context.screen.areas:
        if area.type == screen_type:
            counter += 1
            return_area = area
    if make_sure_only and counter > 1:
        raise Exception("Multiple screen areas found for type: " + screen_type)
    return return_area

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


def push_action_to_nla(rig_obj, name=None):
    """Push 'rig_obj's active action to NLA"""
    act = rig_obj.animation_data.action  # Get current action
    track = rig_obj.animation_data.nla_tracks.new()  # create new NLA track and push action to it
    track.strips.new(act.name, int(act.frame_range[0]), act)
    if name:
        track.name = name
    rig_obj.animation_data.action = None  # Unlink the action as active action


def mute_all_nla_tracks(rig_obj):
    for track in rig_obj.animation_data.nla_tracks:
        track.mute = True


def delete_action_from_nla(action, obj):
    """Deletes any nla track (not just the strip) that has a strip with 'action'.

    'action' is the bpy action object to search and delete nla track for.
    'obj' is the object that has the nla track to search"""
    trs_to_delete = []  # Indices of nla tracks that have action
    for i, tr in enumerate(obj.animation_data.nla_tracks):  # iter thru tracks and strips
        for st in tr.strips:
            if st.action is action:
                trs_to_delete.append(i)
    # Just to be safe, deleting nla tracks via their indices (not holding to refs of
    #     the nla tracks themselves since not sure if memory those refs point to
    #     becomes invalid after deleting some elems from nla_tracks collection)
    for i in trs_to_delete[::-1]:  # Going through list backwards to pop last elem first
        tr = obj.animation_data.nla_tracks[i]
        print("    Overwrite: deleting NLA track: " + tr.name + " for action: " + action.name)
        obj.animation_data.nla_tracks.remove(tr)


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

def set_bone_pose_armature_space(armature_obj, bone_name, bone_pose_as):
    """set bone_name bone pose in armature_obj to armature space pose matrix specified in bone_pose_as"""
    b = armature_obj.data.bones[bone_name]
    pb = armature_obj.pose.bones[bone_name]
    bone_rest_as = b.matrix_local
    if b.parent is not None:
        parent_pose_as = pb.parent.matrix
        parent_rest_as = b.parent.matrix_local
        bone_pose_ls = b.convert_local_to_pose(bone_pose_as, bone_rest_as, parent_matrix=parent_pose_as,
                                               parent_matrix_local=parent_rest_as, invert=True)
    else:
        bone_pose_ls = b.convert_local_to_pose(bone_pose_as, bone_rest_as, invert=True)
    pb.location = bone_pose_ls.to_translation()
    pb.rotation_quaternion = bone_pose_ls.to_quaternion()
    pb.scale = bone_pose_ls.to_scale()


def get_fcurve_keyframe_at_frame(frame, fcurve):
    for i, kf in enumerate(fcurve.keyframe_points):
        if math.isclose(kf.co[0], float(frame)):
            return i, kf
    return -1, None

def scale_fcurve_from_midpoint(fcurve, scale_factor):
    curve_min = math.inf
    curve_max = -math.inf
    for kf in fcurve.keyframe_points:
        if kf.co[1] > curve_max: curve_max = kf.co[1]
        if kf.co[1] < curve_min: curve_min = kf.co[1]
    curve_mid = (curve_max + curve_min) / 2.
    for kf in fcurve.keyframe_points:
        kf.co[1] += (kf.co[1] - curve_mid) * (scale_factor - 1.)

