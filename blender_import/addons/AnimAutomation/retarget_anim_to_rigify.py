
import bpy
import blender_auto_common
import mathutils
import copy


# Common helper functions

def get_retgt_props(context):
    try:
        retgt_props = context.blend_data.texts["retarget_anim_props.py"].as_module()
    except Exception as e:
        raise Exception("Error parsing retarget_anim_props.py file") from e
    return retgt_props


def check_retarget_props(retgt_props, check_rig, check_limb_bake_settings=True):
    if not hasattr(retgt_props, 'retarget_bones') or not hasattr(retgt_props, 'limb_ik_bake_settings'):
        raise Exception("retarget_anim_props.py needs to have 'retarget_bones', 'limb_ik_bake_settings' defined")
    bone_list = copy.deepcopy(retgt_props.retarget_bones)
    if check_limb_bake_settings:
        for limb_settings in retgt_props.limb_ik_bake_settings:
            bone_list += limb_settings.get_bone_flat_list()
    for bone_name in bone_list:
        try:
            check_rig.pose.bones[bone_name]
        except KeyError:
            raise Exception("Invalid Retarget Anim Props: Could not find bone: " + bone_name +
                            " in check rig: " + check_rig.name)


# Operators

class CreateAnimRetargetingIntermediateRig(bpy.types.Operator):
    """Creates a duplicate of the control rig with only the retarget bones and constrains control rig bones to copy

    Rokoku's retargeting operator does not work if the control rig to retarget anims to is a library override, so
    this operator will copy all retargeting FK bones (bones that will have the retargeting anim data applied to it)
    from the control rig, so this armature will be the retargeting target. Then will constrain the corresponding
    control rig bones to the bones in the intermediate rig. NOTE: BONES WILL NOT BE PARENTED.

    USER NOTES:
        1) The blend file should have a text blend data object called "retarget_anim_props.py". See description for
            RetargetAnimsToRigify
        2) If rig already exists with same name as intermediate, will be overwritten
        3) User still needs to go in and make parent all the created bones properly"""

    bl_idname = "armature.create_retgt_intermediate_rig"  # How to ref class from blender python
    bl_label = "Anim Retargeting Intermediate Rig"  # Name in operator menu
    bl_options = {'REGISTER', 'UNDO'}  # Registers and enables undo

    ctrl_rig_name: bpy.props.StringProperty(name="Control Rig Name", default="ctrl_rig",
        description="Rig to copy bones from")

    intermediate_rig_suff: bpy.props.StringProperty(name="Intermediate Rig Name Suff", default="_fk_intermediate",
        description="Suffix to append to control rig name for naming the intermediate rig")

    constrain_to_ctrl_rig: bpy.props.BoolProperty(name="Constrain To Ctrl Rig", default=True,
        description="Constrain the intermediate rig bones to their corresponding bones in the ctrl rig")

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def execute(self, context):
        retgt_props = get_retgt_props(context)
        ctrl_rig_obj = context.blend_data.objects[self.ctrl_rig_name]
        check_retarget_props(retgt_props, ctrl_rig_obj, check_limb_bake_settings=False)
        print("Creating Rig")
        bpy.ops.object.armature_add(enter_editmode=True)
        intermediate_rig_obj = context.object
        intermediate_rig_obj.location = mathutils.Vector()
        intermediate_rig_name = self.ctrl_rig_name + self.intermediate_rig_suff
        intermediate_rig_obj.name = intermediate_rig_name
        intermediate_rig_obj.data.name = intermediate_rig_name

        for b in reversed(intermediate_rig_obj.data.edit_bones):
            intermediate_rig_obj.data.edit_bones.remove(b)

        # Populate intermediate bones and position
        print("Populating Bones ...")
        ctrl_rig_obj = context.blend_data.objects[self.ctrl_rig_name]  # since switched context re-get this
        for rb in retgt_props.retarget_bones:
            print("    " + rb)
            intermediate_rig_obj.data.edit_bones.new(rb)
            # need to use armature space transforms below since intermediate rig bones will not be parented, not _local
            #   suffixes below for ctrl_rig_bones means armature space not local space (very confusing)
            # using matrix as it's important to set bone roll
            intermediate_rig_obj.data.edit_bones[rb].matrix = ctrl_rig_obj.data.bones[rb].matrix_local
            intermediate_rig_obj.data.edit_bones[rb].length = ctrl_rig_obj.data.bones[rb].length
        for rb in retgt_props.retarget_bones:  # NEED TO RUN THIS TWICE - I don't know why lol
            intermediate_rig_obj.data.edit_bones[rb].matrix = ctrl_rig_obj.data.bones[rb].matrix_local
            intermediate_rig_obj.data.edit_bones[rb].length = ctrl_rig_obj.data.bones[rb].length
        print("Bone Population Complete")

        # Constrain control rig
        print("Applying Control Rig Constraints ...")
        blender_auto_common.switch_to_mode(ctrl_rig_obj, "POSE", context=context)
        intermediate_rig_obj = context.blend_data.objects[intermediate_rig_name]
        ctrl_rig_obj = context.blend_data.objects[self.ctrl_rig_name]
        for bone in ctrl_rig_obj.pose.bones:
            if bone.name not in retgt_props.retarget_bones:
                continue
            print("Constraining: " + bone.name)
            loc_const_name = blender_auto_common.anim_retgt_intermediate_rig_constraint_pref + "Loc"
            rot_const_name = blender_auto_common.anim_retgt_intermediate_rig_constraint_pref + "Rot"
            for con in bone.constraints:  # remove all current constraints
                print("    Removing Constraint: " + con.type + ": " + con.name)
                bone.constraints.remove(con)
            print("    Adding Constraint: " + loc_const_name)
            loc = bone.constraints.new(type="COPY_LOCATION")
            loc.name = loc_const_name
            loc.target = intermediate_rig_obj
            loc.subtarget = bone.name
            print("    Adding Constraint: " + rot_const_name)
            rot = bone.constraints.new(type="COPY_ROTATION")
            rot.name = rot_const_name
            rot.target = intermediate_rig_obj
            rot.subtarget = bone.name
        print("Finished applying game rig constraints")
        blender_auto_common.move_obj_to_coll(context, intermediate_rig_obj, "Extra")
        return {'FINISHED'}

    def invoke(self, context, event):
        """Display a pop-up menu to let user set props (called by blender)"""
        return context.window_manager.invoke_props_dialog(self)


class RetargetAnimsToRigify(bpy.types.Operator):
    """Retargets all SELECTED animations in NLA Tracks of a specified armature to this Rigify rig's NLA Tracks.

    USER NOTES:
    1) Rokoku plug in should already be set up for retargeting, e.g. source and dest rigs should have been identified
        and bone list should have already been built
    2) The retargeted actions will be named according to their NLA track name, only one action per track!
    3) The blend file should have a text blend data object called "retarget_anim_props.py" that is a python module with
        the following variables defined:
            a) retarget_bones : string list of rigify FK bone names that retargeted animation
             will be baked to, these bone names should match rokoku retarget Bone List
            b) limb_ik_bake_settings : rigify limb parent bone names for each limb, which is the bone that
            controls IK-FK switch functionality for each limb
    3) The Rigify rig to needs to be the one in pose mode when this operator is run
    4) If use rest pose asset not enabled, will assume that current pose between source and dest armature are
        corresponding, or "Rest Pose" retargeting option selected and are corresponding. If use rest pose asset is
        enabled, see description below """

    bl_idname = "anim.retarget_anims_to_rigify"  # How to ref class from blender python
    bl_label = "Retarget Animations to Rigify"  # Name in operator menu
    bl_options = {'REGISTER', 'UNDO'}  # Registers and enables undo

    #  Below properties control how the operator performs
    source_arm: bpy.props.StringProperty(name="Source Armature", default="src_armature",
        description="Armature that has source animation data to retarget selected in NLA tracks")

    dest_intermediate_rig_suff: bpy.props.StringProperty(name="Dest Rig Intermediate Suff", default="_fk_intermediate",
         description="If rigify rig to retarget animations to is library override, will need to first retarget" 
                     " animation to an intermediate of the rig, then bake unto library override rig. If not retargeting"
                     " animation to library override rig, make this an empty string")

    use_rest_pose_asset: bpy.props.BoolProperty(name="Use Rest Pose", default=True,
        description="Applies a custom pose asset prior to rokoko retargeting to both source and dest rigs that should"
                    "put the two rigs into an identical rest pose. Useful for when source and dest rigs have different"
                    "default rest poses (e.g. A-Pose vs T-Pose). There should be two pose assets defined with names"
                    "_rest_[source_armature] and _rest_[dest_armature].")

    overwrite: bpy.props.BoolProperty(name="Overwrite", default=False,
        description="Whether to overwrite any actions that have the same name that the baked action will have")

    clean_curves: bpy.props.BoolProperty(name="Clean Curves", default=False,
        description="See blender documentation for curve cleaning")

    bake_limb_ik: bpy.props.BoolProperty(name="Bake Limb IK", default=True,
         description="Bake rigify IK controls with FK retargeted animation")

    def user_input_checks(self, context):
        if not hasattr(bpy.ops, 'rsl'):
            raise Exception("Rokoku plugin not installed")
        if not hasattr(bpy.ops, 'rigify'):
            raise Exception("Rigify plugin not installed")
        if context.scene.objects.find(self.source_arm) < 0:
            raise Exception("Could not find source armature " + self.source_arm)
        if context.blend_data.texts.find("retarget_anim_props.py") < 0:
            raise Exception("No 'retarget_anim_props.py' text data for current blend file")
        if self.use_rest_pose_asset:
            if context.blend_data.actions.find("__rest_" + self.source_arm) < 0:
                raise Exception("No rest pose asset with '__rest_' prefix for: " + self.source_arm)

    def get_dest_and_intermediate_rig(self, context):
        dest_rig_obj = blender_auto_common.find_object_in_mode('POSE', context=context)
        dest_intermediate_rig_obj = None
        if len(self.dest_intermediate_rig_suff) > 0:
            dest_intermediate_rig = dest_rig_obj.name + self.dest_intermediate_rig_suff
            if context.scene.objects.find(dest_intermediate_rig) < 0:
                raise Exception("Could not find destination rigify intermediate rig " + dest_intermediate_rig)
            dest_intermediate_rig_obj = context.scene.objects[dest_intermediate_rig]
        if self.use_rest_pose_asset:
            retgt_dist_obj_name = dest_intermediate_rig_obj.name if dest_intermediate_rig_obj else dest_rig_obj.name
            if context.blend_data.actions.find("__rest_" + retgt_dist_obj_name) < 0:
                raise Exception("No rest pose asset with '__rest_' prefix for: " + retgt_dist_obj_name)
        return dest_rig_obj, dest_intermediate_rig_obj

    @staticmethod
    def apply_rest_pose_asset(context, source_arm_obj, retgt_dest_rig):
        blender_auto_common.switch_to_mode(source_arm_obj, 'POSE')
        bpy.ops.pose.select_all()
        context.object.pose.apply_pose_from_action(context.blend_data.actions["__rest_" + source_arm_obj.name])
        blender_auto_common.switch_to_mode(retgt_dest_rig, 'POSE')
        bpy.ops.pose.select_all()
        context.object.pose.apply_pose_from_action(context.blend_data.actions["__rest_" + retgt_dest_rig.name])
        blender_auto_common.switch_to_mode(source_arm_obj, 'OBJECT')
        context.view_layer.update()

    @staticmethod
    def select_all_retarget_bones(retarget_bones, dest_rig):
        """Select all bones that have retargeted anim data baked unto them"""
        for bone_name in retarget_bones:
            dest_rig.pose.bones[bone_name].bone.select = True

    @staticmethod
    def set_rigify_limb_ik_fk(limb_ik_bake_settings, dest_rig, val):
        """Set the rigify rig(s) limbs IK-FK influence to val: 0 - fully IK; 1 - fully FK"""
        print("    Setting limb IK-FK to " + str(val))
        for limb_settings in limb_ik_bake_settings:
            dest_rig.pose.bones[limb_settings.prop_bone]['IK_FK'] = float(val)

    def check_if_retarget_anim_already_exists(self, context, source_anim_name, retgt_action_name):
        if len(self.dest_intermediate_rig_suff) > 0:
            retgt_intermediate_action_ind = context.blend_data.actions.find(source_anim_name + " Retarget")
            if retgt_intermediate_action_ind >= 0:
                print("    Overwriting retargeted anim on intermediate rig: " + source_anim_name + " Retarget")
                context.blend_data.actions.remove(context.blend_data.actions[retgt_intermediate_action_ind])
        retgt_action_ind = context.blend_data.actions.find(retgt_action_name)
        if retgt_action_ind >= 0:
            if self.overwrite:
                print("    Overwrite: overwriting previously retarget anim on dest rig: " + retgt_action_name)
                context.blend_data.actions.remove(context.blend_data.actions[retgt_action_ind])
            else:
                print("    Overwrite: skipping retarget anim already defined: " + retgt_action_name)
                return True
        return False

    def bake_anim_from_intermediate_rig_to_dest(self, context, dest_rig_obj, retgt_props, frame_start, frame_end):
        print("    Baking retargeted animation from intermediate rig to dest rig")
        blender_auto_common.toggle_rig_constraints(True, dest_rig_obj,
                                                   blender_auto_common.anim_retgt_intermediate_rig_constraint_pref,
                                                   retgt_props.retarget_bones)
        print("    Baking complete")
        self.select_all_retarget_bones(retgt_props.retarget_bones, dest_rig_obj)
        retgt_action = context.blend_data.actions.new("New")
        dest_rig_obj.animation_data.action = retgt_action
        dest_rig_obj.select_set(True)  # due to a bug in blender need to make sure bake to rig is selected prior to bake
        bpy.ops.nla.bake(frame_start=frame_start, frame_end=frame_end, visual_keying=True,
                         use_current_action=True, clean_curves=self.clean_curves, only_selected=True)
        context.view_layer.update()
        blender_auto_common.toggle_rig_constraints(False, dest_rig_obj,
                                                   blender_auto_common.anim_retgt_intermediate_rig_constraint_pref,
                                                   retgt_props.retarget_bones)

    @staticmethod
    def clean_up_joint_tgt(context, dest_rig_obj, limb_ik, frame_start, frame_end):
        print("            Cleaning Joint Tgt")
        fk_bones = limb_ik.parse_string_list(limb_ik.fk_bones)
        upper_fk = fk_bones[0]
        lower_fk = fk_bones[1]
        joint_tgt = limb_ik.parse_string_list(limb_ik.ctrl_bones)[1]
        for fr in range(frame_start, frame_end + 1):
            context.scene.frame_set(fr)
            context.view_layer.update()
            v1 = dest_rig_obj.pose.bones[upper_fk].vector
            v2 = dest_rig_obj.pose.bones[lower_fk].vector
            v1_v2 = v1 + v2
            v1_v2.normalize()
            n = v1.cross(v2)
            n.normalize()
            b = v1_v2.cross(n)
            joint_tgt_loc_as = dest_rig_obj.pose.bones[upper_fk].tail + b * 0.75
            blender_auto_common.set_bone_pose_armature_space(dest_rig_obj, joint_tgt,
                 mathutils.Matrix.LocRotScale(joint_tgt_loc_as, None, None))
            context.view_layer.update()
            dest_rig_obj.pose.bones[joint_tgt].keyframe_insert('location')

    def execute(self, context):
        print("Retargeting actions ...")
        context.scene.tool_settings.use_keyframe_insert_auto = False
        self.user_input_checks(context)
        dest_rig_obj, dest_intermediate_rig_obj = self.get_dest_and_intermediate_rig(context)
        source_arm_obj = context.scene.objects[self.source_arm]
        retgt_props = get_retgt_props(context)
        check_retarget_props(retgt_props, dest_rig_obj)
        if dest_intermediate_rig_obj:
            check_retarget_props(retgt_props, dest_intermediate_rig_obj, check_limb_bake_settings=False)
        self.set_rigify_limb_ik_fk(retgt_props.limb_ik_bake_settings, dest_rig_obj, 1.)
        context.view_layer.update()
        dest_rig_id = dest_rig_obj.data['rig_id']

        for source_track in source_arm_obj.animation_data.nla_tracks:
            if not source_track.select:
                continue
            if not source_track:
                continue
            if len(source_track.strips) < 1:
                print("Skipping: " + source_track.name + ", does not have any action strips")
                continue

            blender_auto_common.switch_to_mode(source_arm_obj, 'OBJECT')  # MODE SWITCH: OBJECT ~~~~~~~~~~~~~~~~~~~~~~~~

            retgt_path = source_track.strips[0].action.name + " [" + source_arm_obj.name + "] --> "
            if dest_intermediate_rig_obj:
                retgt_path += source_track.strips[0].action.name + " Retarget [" + \
                              dest_intermediate_rig_obj.name + "] --> "
            retgt_path += source_track.name + " [" + dest_rig_obj.name + "]"
            print("Retargeting action: " + retgt_path)
            source_arm_obj.animation_data.action = source_track.strips[0].action
            frame_start, frame_end = source_arm_obj.animation_data.action.frame_range
            if self.check_if_retarget_anim_already_exists(context, source_track.strips[0].action.name,
                                                          source_track.name):
                continue
            if self.use_rest_pose_asset:
                self.apply_rest_pose_asset(context, source_arm_obj,
                                           dest_intermediate_rig_obj if dest_intermediate_rig_obj else dest_rig_obj)
            print("....Calling Rokoku retargeting plug in...........................................................")
            bpy.ops.rsl.retarget_animation()
            context.view_layer.update()
            print("....Rokoku retarging plug in operation complete..................................................")
            blender_auto_common.switch_to_mode(dest_rig_obj, "POSE")  # MODE SWITCH: SRC_ARMATURE POSE ~~~~~~~~~~~~~~~~
            if dest_intermediate_rig_obj:
                self.bake_anim_from_intermediate_rig_to_dest(context, dest_rig_obj, retgt_props, int(frame_start),
                                                             int(frame_end))
            dest_rig_obj.animation_data.action.name = source_track.name
            dest_rig_obj.animation_data.action.use_fake_user = True
            ik_bake_func = getattr(bpy.ops.pose, 'rigify_limb_ik2fk_bake_' + dest_rig_id)
            if self.bake_limb_ik:
                print("    Baking IK Controls ...")
                for limb_settings in retgt_props.limb_ik_bake_settings:
                    print("        For Limb: " + limb_settings.ik_bones)
                    ik_bake_func(prop_bone=limb_settings.prop_bone,
                                 fk_bones=limb_settings.fk_bones,
                                 ik_bones=limb_settings.ik_bones,
                                 ctrl_bones=limb_settings.ctrl_bones,
                                 tail_bones=limb_settings.tail_bones,
                                 extra_ctrls=limb_settings.extra_ctrls)
                    self.clean_up_joint_tgt(context, dest_rig_obj, limb_settings, int(frame_start), int(frame_end))
                    print("        Limb Bake Complete")
            blender_auto_common.push_action_to_nla(dest_rig_obj)
            dest_rig_obj.animation_data.nla_tracks[-1].mute = True
            if dest_intermediate_rig_obj:
                blender_auto_common.push_action_to_nla(dest_intermediate_rig_obj)
                dest_intermediate_rig_obj.animation_data.nla_tracks[-1].mute = True
                dest_intermediate_rig_obj.animation_data.nla_tracks[-1].name = source_track.name
            source_arm_obj.animation_data.action = None
        print("Finished Retargeting actions")
        return {'FINISHED'}

    def invoke(self, context, event):
        """Display a pop-up menu to let user set props (called by blender)"""
        return context.window_manager.invoke_props_dialog(self)


def pose_menu_func(self, _):
    """Draws pose menu (passed to blender) for this operator"""
    self.layout.operator(RetargetAnimsToRigify.bl_idname)


def armature_add_menu_func(self, _):
    """Draws menu (passed to blender)"""
    self.layout.operator(CreateAnimRetargetingIntermediateRig.bl_idname)


def register():
    """Registers this add-on to blender if user selected (called by blender)"""
    bpy.utils.register_class(RetargetAnimsToRigify)
    bpy.utils.register_class(CreateAnimRetargetingIntermediateRig)


def unregister():
    """Unregisters this add-on is user de-selected"""
    bpy.utils.unregister_class(RetargetAnimsToRigify)
    bpy.utils.unregister_class(CreateAnimRetargetingIntermediateRig)


if __name__ == '__main__':
    register()
