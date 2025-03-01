import re
from collections import defaultdict

from django.db.models import ObjectDoesNotExist
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.fields import CharField, FloatField, ListField, RegexField
from rest_framework.serializers import ModelSerializer, Serializer, SerializerMethodField

from core.utils.constants import YOUTUBE_VIDEO_ID_REGEX
from tournesol.entities.base import UID_DELIMITER
from tournesol.entities.video import YOUTUBE_UID_NAMESPACE, VideoEntity
from tournesol.models import Entity, EntityCriteriaScore
from tournesol.utils.api_youtube import VideoNotFound


class VideoSerializer(ModelSerializer):
    video_id = RegexField(
        rf"^({YOUTUBE_VIDEO_ID_REGEX})$",
        source="metadata.video_id",
        help_text="Video ID from YouTube URL, matches ^[A-Za-z0-9-_]{11}$",
    )
    name = serializers.CharField(
        source="metadata.name",
        read_only=True,
        help_text="Video title",
    )
    description = serializers.CharField(
        source="metadata.description",
        read_only=True,
        allow_null=True,
        help_text="Video description, from YouTube",
    )
    publication_date = serializers.DateField(
        source="metadata.publication_date",
        read_only=True,
        allow_null=True,
    )
    views = serializers.IntegerField(
        source="metadata.views", read_only=True, allow_null=True
    )
    uploader = serializers.CharField(
        source="metadata.uploader",
        read_only=True,
        allow_null=True,
        help_text="Name of the channel on YouTube",
    )
    language = serializers.CharField(
        source="metadata.language", read_only=True, allow_null=True
    )
    duration = serializers.IntegerField(
        source="metadata.duration", read_only=True, allow_null=True
    )

    class Meta:
        model = Entity
        fields = [
            "uid",
            "name",
            "description",
            "publication_date",
            "views",
            "uploader",
            "language",
            "rating_n_ratings",
            "rating_n_contributors",
            "duration",
            # backward compatibility
            "video_id",
        ]
        read_only_fields = [
            "uid",
            "rating_n_ratings",
            "rating_n_contributors",
        ]

    def validate_video_id(self, value):
        if Entity.objects.filter(
            uid=f"{YOUTUBE_UID_NAMESPACE}{UID_DELIMITER}{value}"
        ).exists():
            raise ValidationError("A video with this video_id already exists")
        return value

    def create(self, validated_data):
        try:
            return Entity.create_from_video_id(validated_data["metadata"]["video_id"])
        except VideoNotFound:
            raise NotFound("The video has not been found. `video_id` may be incorrect.")


class RelatedVideoSerializer(VideoSerializer):
    """
    A video serializer that will create the Entity object on validation
    if it does not exist in the database yet.

    Used by ModelSerializer(s) having one or more nested relations with Entity,
    and having the constraint to ensure that video instances exist before
    they can be saved properly.
    """

    video_id = RegexField(rf"^({YOUTUBE_VIDEO_ID_REGEX})$")

    def validate_video_id(self, value):
        try:
            Entity.get_from_video_id(video_id=value)
        except ObjectDoesNotExist:
            try:
                Entity.create_from_video_id(value)
            except VideoNotFound:
                raise ValidationError(
                    "The video has not been found. `video_id` may be incorrect."
                )
        return value


class EntityCriteriaScoreSerializer(ModelSerializer):
    class Meta:
        model = EntityCriteriaScore
        fields = ["criteria", "score"]


class VideoSerializerWithCriteria(VideoSerializer):
    criteria_scores = EntityCriteriaScoreSerializer(many=True)

    class Meta(VideoSerializer.Meta):
        # XXX: the `tournesol_score` field is available directly in the
        # Entity model for now, but will be moved in an n-n relation
        # between Entity and Poll
        fields = VideoSerializer.Meta.fields + ["tournesol_score", "criteria_scores"]

        # Overriding 'read_only_fields' should not be necessary here. However, due to a
        # limitation in DRF, some extra attributes from model fields (nullable, etc.) are
        # not present in the schema generated by drf-spectacular for read_only fields.
        # See https://github.com/tfranzel/drf-spectacular/issues/383 for more details.
        # This serializer is always used as read-only, so the 'read_only_fields' definition
        # can be discarded safely to generate a correct OpenAPI schema.
        read_only_fields = ["tournesol_score"]


class EntityPollSerializer(serializers.Serializer):
    name = serializers.CharField()
    criteria_scores = EntityCriteriaScoreSerializer(many=True)


class EntitySerializer(ModelSerializer):
    """
    An Entity serializer that also includes polls.

    Use `EntityNoExtraFieldSerializer` if you don't need the related polls.
    """

    polls = serializers.SerializerMethodField()

    class Meta:
        model = Entity
        fields = [
            "uid",
            "type",
            "metadata",
            # XXX: the `tournesol_score` field is available directly in the
            # Entity model for now, but will be moved in an n-n relation
            # between Entity and Poll
            "tournesol_score",
            "polls",
        ]
        read_only_fields = [
            # XXX: the `tournesol_score` field is available directly in the
            # Entity model for now, but will be moved in an n-n relation
            # between Entity and Poll
            "tournesol_score"
        ]

    @extend_schema_field(EntityPollSerializer(many=True))
    def get_polls(self, obj):
        poll_to_scores = defaultdict(list)
        for score in obj.criteria_scores:
            poll_to_scores[score.poll.name].append(score)
        items = [
            {"name": name, "criteria_scores": scores}
            for (name, scores) in poll_to_scores.items()
        ]
        return EntityPollSerializer(items, many=True).data


class CriteriaDistributionScoreSerializer(Serializer):

    criteria = CharField()
    distribution = ListField(child=FloatField())
    bins = ListField(child=FloatField())


class EntityCriteriaDistributionSerializer(EntitySerializer):
    """
    An Entity serializer that show distribution of score for a given entity
    """

    criteria_scores_distributions = SerializerMethodField()

    class Meta:
        model = Entity
        fields = [
            "uid",
            "type",
            "metadata",
            "tournesol_score",
            "rating_n_contributors",
            "criteria_scores_distributions"
        ]
        read_only_fields = [
            "uid",
            "type",
            "metadata",
            "tournesol_score",
            "rating_n_contributors",
            "criteria_scores_distributions"
        ]

    @extend_schema_field(CriteriaDistributionScoreSerializer(many=True))
    def get_criteria_scores_distributions(self, obj):
        return CriteriaDistributionScoreSerializer(
            obj.criteria_scores_distributions(poll=self.context["poll"]),
            many=True).data


class EntityNoExtraFieldSerializer(EntitySerializer):
    """
    An Entity serializer that doesn't include extra fields.
    """

    class Meta:
        model = Entity
        fields = [
            "uid",
            "type",
            "metadata",
        ]
        read_only_fields = [
            "uid",
            "type",
            "metadata",
        ]


class RelatedEntitySerializer(EntitySerializer):
    """
    An Entity serializer that will lookup and possibly create the Entity
    object on validation, if it does not exist in the database yet.

    Only the field `uid` is provided when using write HTTP methods.

    Used by ModelSerializer(s) having one or more nested relations with Entity,
    and having the constraint to ensure that entity instances exist before
    they can be saved properly.
    """

    uid = CharField(max_length=144)

    class Meta:
        model = Entity
        fields = [
            "uid",
            "type",
            "metadata",
        ]
        read_only_fields = [
            "type",
            "metadata",
        ]

    def validate_uid(self, value):
        """
        Validate the `uid` against the regex provided by the entity class.
        """
        split_uid = value.split(UID_DELIMITER)

        if len(split_uid) <= 1 or not split_uid[1]:
            raise ValidationError("Malformed `uid`.")

        poll = self.context["poll"]
        regex = poll.entity_cls.get_uid_regex(split_uid[0])

        if not regex:
            raise ValidationError(f"Unknown `uid` namespace: {split_uid[0]}")

        if not re.fullmatch(regex, value):
            raise ValidationError("This value does not match the required pattern.")

        return value

    def validate(self, data):
        uid = data.get("uid")
        try:
            Entity.objects.get(uid=uid)
        except ObjectDoesNotExist:
            created = False
            if self.context["poll"].entity_type == VideoEntity.name:
                # A video entity can be created dynamically from a YouTube video id
                video_id = uid.split(UID_DELIMITER)[1]
                try:
                    Entity.create_from_video_id(video_id)
                    created = True
                except VideoNotFound:
                    pass
            if not created:
                raise ValidationError("The entity has not been found. `uid` may be incorrect.")

        return data
