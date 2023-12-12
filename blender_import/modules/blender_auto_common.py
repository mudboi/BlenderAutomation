import bpy


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
    export_col = None
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
