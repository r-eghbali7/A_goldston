from django.urls import path

from . import views

app_name = "blog"

urlpatterns = [
    # ====== Post List ======
    path(
        "",
        views.PostListView.as_view(),
        name="post_list",
    ),
    path(
        "category/<slug:category_slug>/",
        views.PostListView.as_view(),
        name="post_list_by_category",
    ),
    path(
        "tag/<slug:tag_slug>/",
        views.PostListView.as_view(),
        name="post_list_by_tag",
    ),

    # ====== Post Detail ======
    path(
        "post/<slug:slug>/",
        views.PostDetailView.as_view(),
        name="post_detail",
    ),

    # ====== Comments ======
    path(
        "post/<int:post_id>/comment/",
        views.comment_form,
        name="comment_form",
    ),

    # ====== Short Link ======
    path(
        "s/<slug:short_code>/",
        views.short_link_redirect,
        name="short_link_redirect",
    ),

    # ====== N8N API ======
    path(
        "api/n8n/post/<slug:slug>/",
        views.PostDetailN8nAPIView.as_view(),
        name="n8n_post_detail",
    ),

    # ====== Live Search ======
    path(
        "api/v1/live-search/",
        views.live_search_posts,
        name="live_search",
    ),
]
