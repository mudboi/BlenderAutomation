import bpy
import math
import mathutils
import warnings
import blender_auto_common


def create_idle_poses_from_anim(anim_name, pose_frame, app_name, prefix=True, length=100,
                                push_down=True):
    """Creates an idle animation from a specific pose in an animation with noise fcurve modifiers.

    Note: this func assumes safety keyframes (first keyframes) are set at Frame 1, and that there
    is a pose bone called 'grip' that needs a noise mod on it.

    :param anim_name: action to create idle anims from
    :param pose_frame: frame that has desired idle pose
    :param app_name: string to append to the end of created idle animation name to distinguish it
    :param prefix: If true, will match anim_name as a prefix, making idle poses for all actions that
            begin with 'anim_name', if False, will try to match entire name
    :param length: desired length of idle pose
    :param push_down: push down animations into NLA track
    """

    rig_obj = blender_auto_common.find_object_in_mode('POSE')  # Get current pose mode rig0
    rig_obj.animation_data.action = None  # unlink any actions currently in dope sheet

    for action in bpy.data.actions:
        #  Find the animation to create the idle pose from either thru prefix or full name match
        if prefix:
            if action.name[:len(anim_name)] != anim_name:
                continue
        else:
            if action.name != anim_name:
                continue
        ac = action.copy()  # Copy that animation, this will be the idle action
        ac.name = action.name + app_name
        # Adjusting keyframes so that we preserve the safety keyframes (all keyframes set at Fram 1)
        #     then finding all keyframes on 'pose_frame' and moving them over to frame 1, overwriting
        #     the safety keyframes on those channels that have keyframes on 'pose_frame'
        for fcurve in ac.fcurves:
            kf_to_move_ind = -1
            for i, kf in enumerate(fcurve.keyframe_points):  # Finding keyframes at 'pose_frame'
                if math.isclose(kf.co.x, pose_frame, abs_tol=0.1):
                    kf_to_move_ind = i
                    break  # find first one that is close enough
            if kf_to_move_ind >= 0:
                # if found a keyframe on 'pose_frame', deleting all other keyframes on channel
                for i in range(0, len(fcurve.keyframe_points))[::-1]:
                    # itterating backwards to since we're deleting things in the collection,
                    #     so need to pop the last items first
                    if i == kf_to_move_ind:
                        continue
                    fcurve.keyframe_points.remove(fcurve.keyframe_points[i])
                # Moving that keyframe on 'pose_frame' to Frame 1 and making control handles
                # even so there isn't any unwanted movement
                fcurve.keyframe_points[0].co_ui.x = 1.0
                fcurve.keyframe_points[0].handle_left.y = fcurve.keyframe_points[0].co.y
                fcurve.keyframe_points[0].handle_right.y = fcurve.keyframe_points[0].co.y
            else:
                # If did not find keyframe on 'pose_frame' on this fcurve, delete all other keyframes
                #     on this channel that are not safety keyframe
                for i in range(0, len(fcurve.keyframe_points))[::-1]:
                    if math.isclose(fcurve.keyframe_points[i].co.x, 1.0, abs_tol=0.1):
                        continue
                    fcurve.keyframe_points.remove(fcurve.keyframe_points[i])
        # Creating a keyframe for 'grip' pose bone at the desired length of the idle anim, and
        #     adding noise fcurve modifiers to that bones quaternion curves
        for i, fcurve in enumerate(ac.fcurves):
            if 'pose.bones["grip"]' in fcurve.data_path:
                fcurve.keyframe_points.insert(frame=length, value=fcurve.keyframe_points[0].co_ui.y)
                if 'pose.bones["grip"].rotation_quaternion' in fcurve.data_path:
                    mod = fcurve.modifiers.new('NOISE')
                    mod.scale = 40.0
                    mod.strength = 0.05
                    mod.phase = i
                    mod.use_restricted_range = True
                    mod.frame_start = 2.0
                    mod.frame_end = length-1
                    mod.blend_in = length/5
                    mod.blend_out = length/5
        if push_down:
            rig_obj.animation_data.action = ac
            blender_auto_common.push_action_to_nla(rig_obj)


def calc_foot_speed(act=None, feet_name='foot_ik'):
    """Calculates travel and speed in X and Y direction of feet IK when on the ground.

    FPS, as taken from render settings, will be used to determine speed.The frames where
    each foot is on the ground must denoted by using Extreme Keframe Type (must axactly 2
    of such keyframes in feet channel)

    :param act: action to calculate foot speeds from
    :param feet_name: name of the feet bones, minus the '.L' or '.R'
    :return: Dictionary containing speeds, distances, and times of feet bones
    """

    fps = bpy.context.scene.render.fps
    rig_obj = blender_auto_common.find_object_in_mode('POSE')  # Get current pose mode rig0
    if act is None:
        act = rig_obj.animation_data.action  # get current action if action=None
    else:
        act = bpy.data.actions[act]
    out = {}
    for ft in [feet_name + '.R', feet_name + '.L']:
        out[ft] = {'x_delta': None, 'y_delta': None, 't_delta': None, 'x_speed': None, 'y_speed': None}
        fc_x = act.fcurves.find('pose.bones["%s"].location' % ft, index=0)
        fc_y = act.fcurves.find('pose.bones["%s"].location' % ft, index=1)
        t_vals = [None, None]
        x_vals = [None, None]
        y_vals = [None, None]
        for kf in fc_x.keyframe_points:
            if kf.type == 'EXTREME':
                if t_vals[0] is None:
                    val_ind = 0
                elif t_vals[1] is None:
                    val_ind = 1
                else:
                    warnings.warn("Found more than two 'EXTREME' Keyframes for loc x f-curve for: %s" % ft)
                    continue
                t_vals[val_ind] = kf.co.x
                x_vals[val_ind] = kf.co.y
                y_vals[val_ind] = fc_y.evaluate(kf.co.x)
        if t_vals[0] is None or t_vals[1] is None:
            warnings.warn("Found less than two 'EXTREME' Keyframes for loc x f-curve for: %s" % ft)
            continue
        out[ft]['x_delta'] = x_vals[1] - x_vals[0]
        out[ft]['y_delta'] = y_vals[1] - y_vals[0]
        out[ft]['t_delta'] = (t_vals[1] - t_vals[0])*1/fps
        out[ft]['x_speed'] = out[ft]['x_delta']/out[ft]['t_delta']
        out[ft]['y_speed'] = out[ft]['y_delta']/out[ft]['t_delta']
        out[ft]['speed_mag'] = math.sqrt(out[ft]['x_speed']**2 + out[ft]['y_speed']**2)
    return out


def blend_feet_locations(act_prefix, move_angle, move_speed, foot_name='foot_ik',
                         feet_timing=((0, 24), (24, 48))):
    """Create an action with feet transforms blended between directional movement actions.

    For locomotion animations, there should be actions defined for four movement directions (Forward,
    Backwards, Left, Right). This will blend between the directions and scale the feet motions according
    to given move speed. Note the directional actions should all share a prefix, e.g. "Walk", and then
    either "F", "B", "L", "R" designators after the prefix indicating the movement direction. Note,
    the blended action will be named: 'act_prefix'_'move_ang;e'

    :param act_prefix: the prefix the identify the directional movement actions (e.g. "Run")
    :param move_angle: angle relative to mesh object that defines movement for blended animation
    :param move_speed: mesh object speed that defines how quickly the feet move
    :param foot_name: name of the feet bones
    :param feet_timing: container with frames where ((LF Down, LF Up), (RF Down, RF Up))
    """

    # Get adjacent move direction action given move_angle and calculate blending weight
    if 0 <= move_angle <= 90:
        weight = move_angle/90
        act1_name = act_prefix + 'F'
        act2_name = act_prefix + 'R'
    elif 90 <= move_angle <= 181:
        weight = (move_angle - 90)/90
        act1_name = act_prefix + 'R'
        act2_name = act_prefix + 'B'
    elif -90 <= move_angle <= 0:
        weight = move_angle/-90
        act1_name = act_prefix + 'F'
        act2_name = act_prefix + 'L'
    elif -181 <= move_angle <= -90:
        weight = (move_angle + 90)/-90
        act1_name = act_prefix + 'L'
        act2_name = act_prefix + 'B'
    else:
        weight = 0
        act1_name = act_prefix + 'F'
        act2_name = act_prefix + 'R'

    weight = max(min(1, weight), 0)
    bones = [foot_name + '.L', foot_name + '.R']
    rig_obj = blender_auto_common.find_object_in_mode('POSE')
    act1 = bpy.data.actions[act1_name]
    act2 = bpy.data.actions[act2_name]
    fps = bpy.context.scene.render.fps

    # Below functions do the actual blending
    def blend_loc(bm1, bm2):
        return bm1.translation * (1 - weight) + bm2.translation * weight

    def blend_rot(bm1, bm2):
        return bm1.to_quaternion().slerp(bm2.to_quaternion(), weight)

    # Step through anim frame by frame, collecting bone transform data from feet bones
    bone_transforms = [[[], []],
                       [[], []]]  # bone_transforms[action][LF or RF]; LF: index 0, RF: index 1
    for i, act in enumerate([act1, act2]):
        rig_obj.animation_data.action = act
        for fr in range(bpy.context.scene.frame_start, bpy.context.scene.frame_end + 2):
            bpy.context.scene.frame_set(fr)
            for j, bone in enumerate(bones):
                pb = rig_obj.pose.bones[bone]
                bone_transforms[i][j].append(pb.matrix.copy())

    # Calculate scale factor needed to scale blended feet movement locations such that the
    #    feet motion speed correspond to move_speed
    scale_fac = []  # LF: index 0, RF: index 1
    midpoints = []
    for j, bone in enumerate(bones):
        down_fr, up_fr = feet_timing[j]
        # First get total feet displacement on ground (delta_loc)
        down_loc = blend_loc(bone_transforms[0][j][down_fr], bone_transforms[1][j][down_fr]).to_2d()
        up_loc = blend_loc(bone_transforms[0][j][up_fr], bone_transforms[1][j][up_fr]).to_2d()
        delta_loc = up_loc - down_loc
        # Calc midpoint (will use this to recenter data when scaling)
        midpoints.append(down_loc + delta_loc/2)
        delta_time = (feet_timing[j][1] - feet_timing[j][0])/fps
        bl_speed = delta_loc.magnitude/delta_time
        scale_fac.append(move_speed/bl_speed)

    # Create new action and blend feet transform, then scale them
    bl_act = bpy.data.actions.new(act_prefix + '_%i' % move_angle)
    rig_obj.animation_data.action = bl_act
    for fr in range(bpy.context.scene.frame_start, bpy.context.scene.frame_end + 2):
        bpy.context.scene.frame_set(fr)
        for j, bone in enumerate(bones):
            mat1 = bone_transforms[0][j][fr]
            mat2 = bone_transforms[1][j][fr]
            mid = midpoints[j].to_3d()
            bl_loc = (blend_loc(mat1, mat2) - mid) * scale_fac[j] + mid
            bl_rot = blend_rot(mat1, mat2)
            bn = rig_obj.pose.bones[bone]
            bn.matrix = mathutils.Matrix.LocRotScale(bl_loc, bl_rot, None)
            bn.keyframe_insert('location')
            bn.keyframe_insert('rotation_quaternion')


def create_anim_bone_transform_xml(filepath, anim_group_dict):
    """ Export bone transforms in anim_group_dict to xml file for use in other programs.

    Can group bone transforms from several animations together, and multiple bones, in a single file.
    Also has support for exporting custom properties for the group and each anim, properties can only be int, float,
    or strings.

    anim_group_dict structure should be:
    {
        'custom_props':    [OPTIONAL]
            {
                'prop1': val1,
                ...
            }

        'anims':
            {
                'ANIM_NAME':
                    {
                        'custom_props':   [OPTIONAL]
                            {
                                'prop1': val1,
                                ...
                            }
                        'bone_tforms':
                            {
                                'BONE_NAME':
                                    {
                                        'num_frame': Number of Frames
                                        'type': one of ['Loc',  'Rot', 'LocRot'] no support for scale, since it
                                        doesn't play well with unreal engine. Note, ordering of Rot elems should be
                                        QX, QY, QZ, QW and for LocRot, Rot elems should be first: QX, QY, QZ, QW,
                                        X, Y, Z.
                                        'data': Float itterable containing bone transform matrix elements flattened
                                    }
                                ....
                            }
                    }
                ...
            }
    }

    :param filepath: file path for xml
    :param anim_group_dict: see above
    """

    def write_custom_props(prop_dict, fhandle, level, tag):
        f.write('\t' * level + '<%s>\n' % tag)
        for key, val in prop_dict.items():
            if type(val) not in [int, float, str]:
                raise Exception('Custom prop val can only be int, float, or string, detected: %s for prop: %s'
                                % (type(val).__name__, key))
            fhandle.write('\t' * (level + 1))
            fhandle.write('<prop name="%s" type="%s">' % (key, type(val).__name__))
            fhandle.write(str(val) + "</prop>\n")
        f.write('\t' * level + '</%s>\n' % tag)

    with open(filepath, 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<animation_group>\n')
        if 'custom_props' in anim_group_dict.keys():
            if anim_group_dict['custom_props']:
                write_custom_props(anim_group_dict['custom_props'], f, 1, 'anim_group_props')
        for anim_name, anim_dict in anim_group_dict['anims'].items():
            f.write('\t<animation name="%s">\n' % anim_name)
            if 'custom_props' in anim_dict.keys():
                if anim_dict['custom_props']:
                    write_custom_props(anim_dict['custom_props'], f, 2, 'anim_props')
            for bone_name, bone_tform_data in anim_dict['bone_tforms'].items():
                f.write('\t\t<bone_transforms bone="%s" num_frames="%i" type="%s">'
                        % (bone_name, bone_tform_data['num_frames'], bone_tform_data['type']))
                for el in bone_tform_data['data']:
                    f.write("%.6f " % el)
                f.write('</bone_transforms>\n')
            f.write('\t</animation>\n')
        f.write('</animation_group>\n')


def export_foot_location_xml(anim_group_name, feet_timing, filepath):
    """Export feet location data and Leg IK targets for a group of locomotion animations for use in Unreal Engine.

    Used for Locomotion Stride Retargeting Sytem for Unreal, so converts to Unreal component frame (LH coordinate frame,
    matches mesh object space but with y axis flipped) and Unreal units (cm instead of m). Also exports feet timing
    data for when the feet are in contact with ground.

    Bones must be named: ['DEF-foot.L', 'DEF-foot.R', 'TGT-thigh_ik_target.L', 'TGT-thigh_ik_target.R']. The animations
    must be named: with a 'F', 'L', 'R', or 'B' as the last character to indicate move direction, and a common
    group name e.g. 'Walk[F, L, R, B]'.

    :param anim_group_name: name prefix indicating locomotion anim group
    :param feet_timing: (LF Down frame, LF Up frame, RF Down frame, RF Up frame)
    :param filepath: where to save the xml file
    """

    fps = bpy.context.scene.render.fps
    rig_obj = blender_auto_common.find_object_in_mode('POSE')
    bone_names = ['DEF-foot.L', 'DEF-foot.R', 'TGT-thigh_ik_target.L', 'TGT-thigh_ik_target.R']
    anims = [(anim_group_name + dir_suff) for dir_suff in ['F', 'L', 'R', 'B']]

    # Build and populate dict used by xml export function above
    bone_transforms =\
        {
            'custom_props':
                {
                    'anim_group_name': anim_group_name,
                    'fps': fps,
                    'lf_down_frame': feet_timing[0],
                    'lf_up_frame': feet_timing[1],
                    'rf_down_frame': feet_timing[2],
                    'rf_up_frame': feet_timing[3]
                },
            'anims': {}
        }
    for anim_name in anims:
        bone_transforms['anims'][anim_name] = {'bone_tforms': {}, 'custom_props': {'direction': anim_name[-1]}}
        for bn in bone_names:
            bone_transforms['anims'][anim_name]['bone_tforms'][bn] = \
                {
                    'num_frames': bpy.context.scene.frame_end + 2,
                    'type': 'Loc',
                    'data': []
                }
        act = bpy.data.actions[anim_name]
        rig_obj.animation_data.action = act
        for fr in range(bpy.context.scene.frame_start, bpy.context.scene.frame_end + 2):
            bpy.context.scene.frame_set(fr)
            for bn in bone_names:
                bn_vec = rig_obj.pose.bones[bn].matrix.translation.copy()
                bn_vec[1] = - bn_vec[1]
                bn_vec = 100 * bn_vec
                for el in bn_vec:
                    bone_transforms['anims'][anim_name]['bone_tforms'][bn]['data'].append(el)
    create_anim_bone_transform_xml(filepath, bone_transforms)

def clear_action_stash():
    rig_obj = blender_auto_common.find_object_in_mode('POSE')
    nla_tracks = rig_obj.animation_data.nla_tracks
    for track in nla_tracks:
        if '[Action Stash]' in track.name:
            nla_tracks.remove(track)