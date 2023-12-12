# USER NOTES:
#   1) Will only bake actions that are selected for the cntrl rig
#   1) The baked actions will be named as (prefix + strip name in of first strip in nla track)


bl_info = {
    "name": "Batch Bake Anims to Rig",
    "author": "Inderbir Sidhu",
    "version": (1, 0, 4),
    "blender": (2, 93, 0),
    "location": "View3D > Pose > Batch Animation Bake to Rig",
    "description": "Bakes all selected animations in NLA Tracks of a Rig to another Rig's NLA Tracks",
    "warning": "",
    "category": "Animation",
}


import bpy
import math
import blender_auto_common



class BatchBakeAnimsToRig(bpy.types.Operator):
    """Bakes all SELECTED animations in NLA Tracks of another Rig this rig's NLA Tracks to this rig.
    Note baked animations are named: [prefix][name of first strip in NLA track]"""

    bl_idname = "anim.batch_bake_anims_to_rig"  # How to ref class from blender python
    bl_label = "Batch Animation Bake to Rig"  # Name in operator menu
    bl_options = {'REGISTER', 'UNDO'}  # Registers and enables undo

    #  Below properties control how the operator performs
    ctrl_rig_name: bpy.props.StringProperty(
        name="Anim. Rig Name", default="ctrl_rig", description="Rig that has animation data" +
                                                               " in NLA track to bake to this rig")
    prefix: bpy.props.StringProperty(
        name="Baked Anim Prefix", default="A_", description="Prefix to add to baked animation name")

    overwrite: bpy.props.BoolProperty(
        name="Overwrite", default=False, description="Whether to overwrite any actions that have" +
                                                     "the same name that the baked action will have")

    clean_curves: bpy.props.BoolProperty(
        name="Clean Curves", default=True, description="See blender documentation for curve cleaning")

    remove_root_motion: bpy.props.BoolProperty(
        name="Remove Root Motion", default=False, description="Removes all but first key frame for root bone")

    send_to_ue: bpy.props.BoolProperty(
        name="Send To Unreal", default=True, description="Automatically sends all active NLA strips to UE")

    @staticmethod
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
            obj.animation_data.nla_tracks.remove(obj.animation_data.nla_tracks[i])

    @staticmethod
    def toggle_game_rig_constraints(game_rig_obj, enable):
        """ Toggle game rig loc/rot constraints to ctrl rig on or off depending on enable"""
        for bone in game_rig_obj.pose.bones:
            for cnst in bone.constraints:
                if cnst.type == 'COPY_LOCATION' or cnst.type == 'COPY_ROTATION':
                    cnst.enabled = enable

    def bake_ctrl_rig_track_to_game_rig(self, ctrl_track, game_rig_obj, context):
        """ Bake ctrl_track which should be an NLA track in ctrl rig to game_rig_obj NLA track.

        returns Baked Action or None if not succeeded"""
        if not ctrl_track.select:
            return None
        if len(ctrl_track.strips) < 1:
            print("Skipping: " + ctrl_track.name + ", does not have any action strips")
            return None
        baked_action_name = self.prefix + ctrl_track.strips[0].name
        if context.blend_data.actions.find(baked_action_name) > -1:  # if action already exists with name
            if self.overwrite:  # delete action and any nla tracks containing it
                self.delete_action_from_nla(context.blend_data.actions[baked_action_name], game_rig_obj)
                context.blend_data.actions.remove(context.blend_data.actions[baked_action_name])
            else:
                print("Skipping: " + ctrl_track.strips[0].name + " action already exists, overwrite not enabled")
                return None
        # Get frame extent of track by getting min and max start and end frame of the track's strips
        start = math.inf
        end = -math.inf
        for strip in ctrl_track.strips:
            if strip.frame_start < start:
                start = strip.frame_start
            if strip.frame_end > end:
                end = strip.frame_end
        ctrl_track.is_solo = True  # Isolate animation from track to bake into action
        bpy.ops.nla.bake(frame_start=int(start), frame_end=int(end), only_selected=True,
                         visual_keying=True, clear_constraints=False, clear_parents=False,
                         use_current_action=True, clean_curves=self.clean_curves)
        baked_action = game_rig_obj.animation_data.action
        if baked_action is None:
            print("Skipping: " + ctrl_track.strips[0].name + " Baking action not successful")
        print("Baked action: " + baked_action_name)
        baked_action.name = baked_action_name
        baked_action.use_fake_user = True
        return baked_action

    @staticmethod
    def remove_root_movement(self, baked_action):
            for fcu in baked_action.fcurves:
                if 'pose.bones["root"].' in fcu.data_path:
                    num_kf = len(fcu.keyframe_points)
                    for i, kf in reversed(list(enumerate(fcu.keyframe_points))):
                        if i == 0:
                            continue
                        fcu.keyframe_points.remove(kf)

    @staticmethod
    def mute_all_nla_tracks(rig_obj):
        for track in rig_obj.animation_data.nla_tracks:
            track.mute = True

    def execute(self, context):
        """Bake all selected action in NLA track of ctrl_rig to the rig that is currently in pose mode"""

        if context.scene.objects.find(self.ctrl_rig_name) < 0:
            raise Exception("Could not find ctrl rig: " + self.ctrl_rig_name)
        ctrl_rig_obj = context.scene.objects[self.ctrl_rig_name]
        game_rig_obj = blender_auto_common.find_object_in_mode('POSE', context=context)

        sending_to_unreal = self.send_to_ue
        if self.send_to_ue:
            if game_rig_obj.data is not blender_auto_common.get_export_armature():
                print("Armature recieving baked actions is not the same as Send2UE Export Armature, not sending to UE")
                sending_to_unreal = False
            else:
                self.mute_all_nla_tracks(game_rig_obj)

        self.toggle_game_rig_constraints(game_rig_obj, True)
        bpy.ops.pose.select_all(action='SELECT')  # Need to select all bones to Bake Anim

        # itterate over all NLA tracks in ctrl rig and bake animation from strips to game rig
        for ctrl_track in ctrl_rig_obj.animation_data.nla_tracks:
            baked_action = self.bake_ctrl_rig_track_to_game_rig(ctrl_track, game_rig_obj, context)
            if baked_action is None:
                continue
            if self.remove_root_motion:
                self.remove_root_motion(baked_action)
            blender_auto_common.push_action_to_nla(game_rig_obj)

        if sending_to_unreal:
            self.toggle_game_rig_constraints(game_rig_obj, False)
            print("Sending to Unreal ...")
            try:
                bpy.ops.wm.send2ue()
            except AttributeError:
                print("Can't send to unreal, could not find send2ue addon")
            self.toggle_game_rig_constraints(game_rig_obj, True)
        return {'FINISHED'}

    def invoke(self, context, event):
        """Display a pop-up menu to let user set props (called by blender)"""
        return context.window_manager.invoke_props_dialog(self)


def menu_func(self, context):
    """Draws menu (passed to blender)"""
    self.layout.separator()
    self.layout.operator(BatchBakeAnimsToRig.bl_idname)


def register():
    """Registers this add-on to blender if user selected (called by blender)"""
    bpy.utils.register_class(BatchBakeAnimsToRig)
    bpy.types.VIEW3D_MT_pose.append(menu_func)


def unregister():
    """Unregisters this add-on is user de-selected"""
    bpy.types.VIEW3D_MT_pose.remove(menu_func)
    bpy.utils.unregister_class(BatchBakeAnimsToRig)


if __name__ == '__main__':
    register()
