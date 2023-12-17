
import bpy
import blender_auto_common


bl_info = {
    "name": "Retarget Anims to Rigify",
    "author": "Inderbir Sidhu",
    "version": (1, 0, 0),
    "blender": (3, 3, 1),
    "location": "View3D > Pose > Retarget Anims to Rigify",
    "description": "Retargets all selected anims in NLA Tracks of an armature to Rigify Rig's NLA Tracks",
    "warning": "",
    "category": "Animation"
}


class RetargetAnimsToRigify(bpy.types.Operator):
    """Retargets all SELECTED animations in NLA Tracks of a specified armature to this Rigify rig's NLA Tracks.

    USER NOTES:
    1) Rokoku plug in should already be set up for retargeting, e.g. source and dest rigs should have been identified
        and bone list should have already been built
    2) The retargeted actions will be named according to their NLA track name, only one action per track!
    3) The blend file should have a text blend data object called "RetargetAnimProps.py" that is a python module with
        the following variables defined:
            a) retarget_bones : string list of rigify FK bone names that retargeted animation
             will be baked to, these bone names should match rokoku retarget Bone List
            b) limb_ik_bake_settings : rigify limb parent bone names for each limb, which is the bone that
            controls IK-FK switch functionality for each limb
    3) The Rigify rig to needs to be the one in pose mode when this operator is run
    4) This operator can be found in Pose Mode under Pose sub menu"""

    bl_idname = "anim.retarget_anims_to_rigify"  # How to ref class from blender python
    bl_label = "Retarget Animations to Rigify"  # Name in operator menu
    bl_options = {'REGISTER', 'UNDO'}  # Registers and enables undo

    #  Below properties control how the operator performs
    source_arm: bpy.props.StringProperty(name="Source Armature", default="Armature",
        description="Armature that has source animation data to retarget selected in NLA tracks")

    dest_copy_rig_suff: bpy.props.StringProperty(name="Dest Rig Copy Suff", default="_copy",
         description="If rigify rig to retarget animations to is library override, will need to first retarget" 
                     " animation to a copy of the rig, then bake unto library override rig. If not retargeting"
                     " animation to library override rig, make this an empty string")

    overwrite: bpy.props.BoolProperty(name="Overwrite", default=False,
        description="Whether to overwrite any actions that have the same name that the baked action will have")

    clean_curves: bpy.props.BoolProperty(name="Clean Curves", default=True,
        description="See blender documentation for curve cleaning")

    def user_input_checks(self, context):
        if not hasattr(bpy.ops, 'rsl'):
            raise Exception("Rokoku plugin not installed")
        if not hasattr(bpy.ops, 'rigify'):
            raise Exception("Rigify plugin not installed")
        if context.scene.objects.find(self.source_arm) < 0:
            raise Exception("Could not find source armature " + self.source_arm)
        if context.blend_data.texts.find("RetargetAnimProps.py") < 0:
            raise Exception("No 'RetargetAnimProps.py' text data for current blend file")

    def get_dest_and_copy_rig(self, context):
        dest_rig_obj = blender_auto_common.find_object_in_mode('POSE', context)
        dest_copy_rig_obj = None
        if len(self.dest_copy_rig_suff) > 0:
            dest_copy_rig = dest_rig_obj.name + self.dest_copy_rig_suff
            if context.scene.objects.find(dest_copy_rig) < 0:
                raise Exception("Could not find destination rigify copy rig " + dest_copy_rig)
            dest_copy_rig_obj = context.scene.objects[dest_copy_rig]
        return dest_rig_obj, dest_copy_rig_obj

    @staticmethod
    def get_retgt_props(context):
        try:
            retgt_props = context.blend_data.texts["RetargetAnimProps.py"].as_module()
        except Exception as e:
            raise Exception("Error parsing RetargetAnimProps.py file") from e
        return retgt_props

    @staticmethod
    def check_retarget_props(retgt_props, dest_rig, dest_copy_rig):
        if not hasattr(retgt_props, 'retarget_bones') or not hasattr(retgt_props, 'limb_ik_bake_settings'):
            raise Exception("RetargetAnimProps.py needs to have 'retarget_bones', 'limb_ik_bake_settings' defined")
        bone_list = retgt_props.retarget_bones
        for limb_settings in retgt_props.limb_ik_bake_settings:
            bone_list += limb_settings.get_bone_flat_list()
        for bone_name in bone_list:
            try:
                dest_rig.pose.bones[bone_name]
                if dest_copy_rig: dest_copy_rig.pose.bones[bone_name]
            except KeyError:
                raise Exception("Could not find bone: " + bone_name + " in dest rig or dest copy rig")

    @staticmethod
    def select_all_retarget_bones(retarget_bones, dest_rig):
        """Select all bones that have retargeted anim data baked unto them"""
        for bone_name in retarget_bones:
            dest_rig.pose.bones[bone_name].bone.select = True

    @staticmethod
    def set_rigify_limb_ik_fk(limb_ik_bake_settings, dest_rig, dest_copy_rig, val):
        """Set the rigify rig(s) limbs IK-FK influence to val: 0 - fully IK; 1 - fully FK"""
        print("    Setting limb IK-FK to " + str(val))
        for limb_settings in limb_ik_bake_settings:
            dest_rig.pose.bones[limb_settings.prop_bone]['IK_FK'] = float(val)
            if dest_copy_rig:
                dest_copy_rig.pose.bones[limb_settings.prop_bone]['IK_FK'] = float(val)

    def check_if_retarget_anim_already_exists(self, context, source_anim_name, retgt_action_name):
        if len(self.dest_copy_rig_suff) > 0:
            retgt_copy_action_ind = context.blend_data.actions.find(source_anim_name + " Retarget")
            if retgt_copy_action_ind >= 0:
                print("    Overwriting retargeted anim on copy rig: " + source_anim_name + " Retarget")
                context.blend_data.actions.remove(context.blend_data.actions[retgt_copy_action_ind])
        retgt_action_ind = context.blend_data.actions.find(retgt_action_name)
        if retgt_action_ind >= 0:
            if self.overwrite:
                print("    Overwrite: overwriting previously retarget anim on dest rig: " + retgt_action_name)
                context.blend_data.actions.remove(context.blend_data.actions[retgt_action_ind])
            else:
                print("    Overwrite: skipping retarget anim already defined: " + retgt_action_name)
                return True
        return False

    def bake_anim_from_copy_rig_to_dest(self, context, dest_rig_obj, dest_copy_rig_obj, retgt_props,
                                        frame_start, frame_end):
        print("    Toggling copy rig constraints ON")
        print("    Baking retargeted animation from copy rig to dest rig")
        blender_auto_common.toggle_constrain_bones_rig_to_rig(True, dest_copy_rig_obj, dest_rig_obj,
                                                              retgt_props.retarget_bones, verbose=False)
        print("    Baking complete")
        self.select_all_retarget_bones(retgt_props.retarget_bones, dest_rig_obj)
        retgt_action = context.blend_data.actions.new("New")
        dest_rig_obj.animation_data.action = retgt_action
        dest_rig_obj.select_set(True)  # due to a bug in blender need to make sure bake to rig is selected prior to bake
        bpy.ops.nla.bake(frame_start=frame_start, frame_end=frame_end, visual_keying=True,
                         use_current_action=True, clean_curves=self.clean_curves, only_selected=True)
        blender_auto_common.toggle_constrain_bones_rig_to_rig(False, dest_copy_rig_obj, dest_rig_obj,
                                                              retgt_props.retarget_bones, verbose=False)
        print("    Toggling copy rig constraints OFF")

    def execute(self, context):
        print("Retargeting actions ...")
        self.user_input_checks(context)
        dest_rig_obj, dest_copy_rig_obj = self.get_dest_and_copy_rig(context)
        source_arm_obj = context.scene.objects[self.source_arm]
        retgt_props = self.get_retgt_props(context)
        self.check_retarget_props(retgt_props, dest_rig_obj, dest_copy_rig_obj)
        self.set_rigify_limb_ik_fk(retgt_props.limb_ik_bake_settings, dest_rig_obj, dest_copy_rig_obj, 1.)
        dest_rig_id = dest_rig_obj.data['rig_id']

        for source_track in source_arm_obj.animation_data.nla_tracks:
            if not source_track:
                continue
            if len(source_track.strips) < 1:
                print("Skipping: " + source_track.name + ", does not have any action strips")
                continue
            retgt_path = source_track.strips[0].action.name + " [" + source_arm_obj.name + "] --> "
            if dest_copy_rig_obj:
                retgt_path += source_track.strips[0].action.name + " Retarget [" + dest_copy_rig_obj.name + "] --> "
            retgt_path += source_track.name + " [" + dest_rig_obj.name + "]"
            print("Retargeting action: " + retgt_path)
            source_arm_obj.animation_data.action = source_track.strips[0].action
            frame_start, frame_end = source_arm_obj.animation_data.action.frame_range
            if self.check_if_retarget_anim_already_exists(context, source_track.strips[0].action.name,
                                                          source_track.name):
                continue
            print("    Calling Rokoku retargeting plug in")
            bpy.ops.rsl.retarget_animation() # this pulls us out of pose mode
            print("    Rokoku retarging plug in operation complete")
            dest_rig_obj.select_set(True)  # get back into pose mode with dest rig
            bpy.ops.object.mode_set(mode='POSE')
            if dest_copy_rig_obj:
                self.bake_anim_from_copy_rig_to_dest(context, dest_rig_obj, dest_copy_rig_obj, retgt_props,
                                                     int(frame_start), int(frame_end))
            dest_rig_obj.animation_data.action.name = source_track.name
            dest_rig_obj.animation_data.action.use_fake_user = True
            ik_bake_func = getattr(bpy.ops.pose, 'rigify_limb_ik2fk_bake_' + dest_rig_id)
            print("    Baking IK Controls ...")
            for limb_settings in retgt_props.limb_ik_bake_settings:
                print("        For Limb: " + limb_settings.ik_bones)
                ik_bake_func(prop_bone=limb_settings.prop_bone,
                             fk_bones=limb_settings.fk_bones,
                             ik_bones=limb_settings.ik_bones,
                             ctrl_bones=limb_settings.ctrl_bones,
                             tail_bones=limb_settings.tail_bones,
                             extra_ctrls=limb_settings.extra_ctrls)
                print("        Limb Bake Complete")
            blender_auto_common.push_action_to_nla(dest_rig_obj)
            dest_rig_obj.animation_data.nla_tracks[-1].mute = True
            if dest_copy_rig_obj:
                blender_auto_common.push_action_to_nla(dest_copy_rig_obj)
                dest_copy_rig_obj.animation_data.nla_tracks[-1].mute = True
                dest_copy_rig_obj.animation_data.nla_tracks[-1].mute = source_track.name
            source_arm_obj.animation_data.action = None
        return {'FINISHED'}

    def invoke(self, context, event):
        """Display a pop-up menu to let user set props (called by blender)"""
        return context.window_manager.invoke_props_dialog(self)


def menu_func(self, _):
    """Draws menu (passed to blender)"""
    self.layout.separator()
    self.layout.operator(RetargetAnimsToRigify.bl_idname)


def register():
    """Registers this add-on to blender if user selected (called by blender)"""
    bpy.utils.register_class(RetargetAnimsToRigify)
    bpy.types.VIEW3D_MT_pose.append(menu_func)


def unregister():
    """Unregisters this add-on is user de-selected"""
    bpy.types.VIEW3D_MT_pose.remove(menu_func)
    bpy.utils.unregister_class(RetargetAnimsToRigify)


if __name__ == '__main__':
    register()
