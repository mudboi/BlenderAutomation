
import bpy
import time
import blender_auto_common


class BatchMirrorAnimsLeftRight(bpy.types.Operator):
    """Mirrors all SELECTED animations (actions) in NLA Tracks left to right of the rig that is currently in POSE mode

    USER NOTES:
        1) Each selected action in NLA should be named [_][L or R][ ... the rest of the name], e.g.
           " _LStanceIdle", the created flipped anim will flip the _L to _R and vice versa
        2) The mirrored action will be named as "-" + [L or R FLIPPED][... the rest of the name], so the mirrored
            anim from the above example will be "_RStanceIdle"
        3) For animations that have character moving in a direction, e.g. _RStanceMoveL has character moving to th left,
            when the animation is mirrored, the animation will now have character moving in the opposite direciton, e.g.
            the flipped version of _RStanceMoveL should be _LStanceMoveR. As long as flip_anim_move_dir is True below, for
            every anim that has 'L' or 'R' at the end of the name, it will be flipped to 'R' and 'L' respectively
        4) Pose markers denoting foot down/up frames should be named LF_[Down/Up] or RF_[Down/Up], their naming will
            have to be flipped as well when mirroring animation
        3) This operator can be found in Pose Mode under Pose sub menu.
        4) IMPORTANT: Make sure all bones are selectable"""

    bl_idname = "anim.batch_mirror_anims_leftright"  # How to ref class from blender python
    bl_label = "Batch Mirror Anims Left Right"  # Name in operator menu
    bl_options = {'REGISTER', 'UNDO'}  # Registers and enables undo

    #  Below properties control how the operator performs
    overwrite: bpy.props.BoolProperty(name="Overwrite", default=False,
        description="Whether to overwrite any actions that have the same name that the mirror action will have")

    flip_anim_move_dir: bpy.props.BoolProperty(name="Flip Anim Move Dir", default=True,
        description="If anim has 'L' or 'R' at the end of anim name, will flip the naming to 'R' and 'L', respecively" 
        " as mirrored animation will be moving in the opposite direction")

    def execute(self, context):
        """Mirrors all selected action in NLA track of the rig that is currently in pose mode"""
        rig_obj = blender_auto_common.find_object_in_mode('POSE', context=context)
        view_area = blender_auto_common.get_first_screen_area_of_type('VIEW_3D', context)
        sheet_area = blender_auto_common.get_first_screen_area_of_type('DOPESHEET_EDITOR', context)
        if view_area is None or sheet_area is None:
            raise Exception("Need to have 3D viewport window and dopesheet edit window open to run this operator")

        print("Mirroring actions ...")
        # itterate over all NLA tracks and strips in rig to get actions to mirror from tracks selected
        mirror_acts = []
        for track in rig_obj.animation_data.nla_tracks:
            if not track.select:
                continue
            for strip in track.strips:
                if not strip.action:
                    print("    Skipping strip '" + strip.name + "', no action is linked to it")
                    continue
                flip_name = self.get_flipped_action_name(strip.action.name)
                if not flip_name:
                    print("    Skipping action '" + strip.action.name + "', name not well formatted")
                    continue
                overriden = False
                if context.blend_data.actions.find(flip_name) > -1:  # if action already exists with name
                    if self.overwrite:
                        overriden = True
                        blender_auto_common.delete_action_from_nla(context.blend_data.actions[flip_name], rig_obj)
                        context.blend_data.actions.remove(context.blend_data.actions[flip_name])
                    else:
                        print("    Skipping action '" + strip.action.name + "', action already exists and override not specifed")
                        continue
                mirror_acts.append((strip.action, flip_name, overriden))

        with context.temp_override(area=view_area):
            bpy.ops.pose.select_all(action='SELECT')

        for strip_act, flip_name, overriden in mirror_acts:
            blender_auto_common.mute_all_nla_tracks(rig_obj)
            status_str = "    Mirroring action: '" + strip_act.name + "' -> '" + flip_name + "'"
            if overriden:
                status_str += " [OVERRIDING SAME NAME ACTION]"
            print(status_str)
            flipped_action = strip_act.copy()
            flipped_action.name = flip_name
            rig_obj.animation_data.action = flipped_action
            bpy.context.scene.frame_set(0)
            with context.temp_override(area=sheet_area, region=sheet_area.regions[0]):
                bpy.ops.anim.channels_select_all(action='SELECT')  # VERY IMPORTANT TO SELECT CHANNELS AS WELL AS KEYFRAMES!!!!!!
                bpy.ops.action.select_all(action='SELECT')
                bpy.ops.action.copy()
                bpy.ops.action.paste(merge="OVER_ALL", flipped=True)
            self.flip_pose_markers(flipped_action)
            flipped_action.use_fake_user = True
            blender_auto_common.push_action_to_nla(rig_obj, flipped_action.name)
        print("Finished Mirroring Actions")
        return {'FINISHED'}

    def get_flipped_action_name(self, act_name):
        flip_name = ""
        if act_name[:2] == "_L":
            flip_name = "_R" + act_name[2:]
        elif act_name[:2] == "_R":
            flip_name = "_L" + act_name[2:]
        else:
            return None
        if self.flip_anim_move_dir:
            if flip_name[-1] == 'L':
                flip_name = flip_name[:-1] + 'R'
            elif flip_name[-1] == 'R':
                flip_name = flip_name[:-1] + 'L'
        return flip_name

    @staticmethod
    def flip_pose_markers(flip_action):
        for m in flip_action.pose_markers:
            if m.name[:2] == "LF":
                m.name = "RF" + m.name[2:]
            elif m.name[:2] == "RF":
                m.name = "LF" + m.name[2:]

    def invoke(self, context, event):
        """Display a pop-up menu to let user set props (called by blender)"""
        return context.window_manager.invoke_props_dialog(self)


def pose_menu_func(self, _):
    """Draws pose menu entry for this operator (passed to blender)"""
    self.layout.operator(BatchMirrorAnimsLeftRight.bl_idname)


def register():
    """Registers this add-on to blender if user selected (called by blender)"""
    bpy.utils.register_class(BatchMirrorAnimsLeftRight)


def unregister():
    """Unregisters this add-on is user de-selected"""
    bpy.utils.unregister_class(BatchMirrorAnimsLeftRight)


if __name__ == '__main__':
    register()
