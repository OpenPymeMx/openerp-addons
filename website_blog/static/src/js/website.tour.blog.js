(function () {
    'use strict';

    var website = openerp.website;
    var _t = openerp._t;

    website.EditorBar.include({
        start: function () {
            this.registerTour(new website.Tour.Blog(this));
            return this._super();
        },
    });

    website.Tour.Blog = website.Tour.extend({
        id: 'blog',
        name: "Create a blog post",
        testPath: '/(blog|blogpost)',
        init: function () {
            var self = this;
            self.steps = [
                {
                    title:     _t("New Blog Post"),
                    content:   _t("Let's go through the first steps to write beautiful blog posts."),
                    template:  self.popover({ next: _t("Start Tutorial"), end: _t("Skip") }),
                },
                {
                    element:   '#content-menu-button',
                    placement: 'left',
                    title:     _t("Add Content"),
                    content:   _t("Create new pages, blogs, menu items and products through the <em>'Content'</em> menu."),
                    template:  self.popover({ fixed: true }),
                },
                {
                    element:   'a[data-action=new_blog_post]',
                    placement: 'left',
                    title:     _t("New Blog Post"),
                    content:   _t("Select this menu item to create a new blog post."),
                    template:  self.popover({ fixed: true }),
                },
                {
                    element:   '.modal:has(#editor_new_blog) button.btn-primary',
                    placement: 'bottom',
                    title:     _t("Create Blog Post"),
                    content:   _t("Click <em>Continue</em> to create the blog post."),
                },
                {
                    waitNot:   '.modal',
                    waitFor:   'body:has(button[data-action=save]:visible):has(.js_blog)',
                    title:     _t("Blog Post Created"),
                    content:   _t("This is your new blog post. Let's edit it."),
                    template:  self.popover({ next: _t("Continue") }),
                },
                {
                    element:   'h1[data-oe-expression="blog_post.name"]',
                    placement: 'bottom',
                    sampleText: 'New Blog',
                    title:     _t("Set a Title"),
                    content:   _t("Click on this area and set a catchy title for your blog post."),
                },
                {
                    waitNot:   '#wrap h1[data-oe-model="blog.post"]:contains("Blog Post Title")',
                    element:   'button[data-action=snippet]',
                    placement: 'bottom',
                    title:     _t("Layout Your Blog Post"),
                    content:   _t("Use well designed building blocks to structure the content of your blog. Click 'Insert Blocks' to add new content."),
                    template:  self.popover({ fixed: true }),
                },
                {
                    snippet:   'image-text',
                    placement: 'bottom',
                    title:     _t("Drag & Drop a Block"),
                    content:   _t("Drag the <em>'Image-Text'</em> block and drop it in your page."),
                    template:  self.popover({ fixed: true }),
                },
                {
                    element:   'button[data-action=snippet]',
                    placement: 'bottom',
                    title:     _t("Add Another Block"),
                    content:   _t("Let's add another block to your post."),
                    template:  self.popover({ fixed: true }),
                },
                {
                    snippet:   'text-block',
                    placement: 'bottom',
                    title:     _t("Drag & Drop a block"),
                    content:   _t("Drag the <em>'Text Block'</em> block and drop it below the image block."),
                    template:  self.popover({ fixed: true }),
                },
                {
                    element:   '.oe_active .oe_snippet_remove',
                    placement: 'top',
                    title:     _t("Delete the Title"),
                    content:   _t("From this toolbar you can move, duplicate or delete the selected zone. Click on the garbage can image to delete the title."),
                },
                {
                    waitNot:   '.oe_active .oe_snippet_remove:visible',
                    element:   'button[data-action=save]',
                    placement: 'right',
                    title:     _t("Save Your Blog"),
                    content:   _t("Click the <em>Save</em> button to record changes on the page."),
                    template:  self.popover({ fixed: true }),
                },
                {
                    waitFor:   'button[data-action=edit]:visible',
                    element:   'button.btn-danger.js_publish_btn',
                    placement: 'top',
                    title:     _t("Publish Your Post"),
                    content:   _t("Your blog post is not yet published. You can update this draft version and publish it once you are ready."),
                },
                {
                    waitFor:   '.js_publish_management button.js_publish_btn.btn-success:visible',
                    title:     "Thanks!",
                    content:   _t("This tutorial is finished. To discover more features, improve the content of this page and try the <em>Promote</em> button in the top right menu."),
                    template:  self.popover({ end: _t("Close Tutorial") }),
                },
            ];
            return this._super();
        },
    });

}());
