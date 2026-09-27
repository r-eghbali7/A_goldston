from rest_framework import serializers

from .models import Post


class PostDetailN8nSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source="category.name", read_only=True)
    author = serializers.CharField(source="author.full_name", read_only=True)
    tags = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            "title",
            "slug",
            "url",
            "text",
            "description",
            "read_time",
            "created_date",
            "author",
            "category",
            "tags",
            "image",
        )
        read_only_fields = fields

    def get_tags(self, obj):
        # tags are already prefetched via get_queryset
        return [tag.name for tag in obj.tags.all()]

    def get_image(self, obj):
        request = self.context.get("request")
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None

    def get_url(self, obj):
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.get_absolute_url())
        return obj.get_absolute_url()
