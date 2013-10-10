r.saved = {}

r.saved.SaveCategories = Backbone.Collection.extend({
    url: '/api/savedcategories.json',

    parse: function(response) {
        return response.categories;
    }
})

r.saved.SaveDialog = r.ui.Bubble.extend({
    confirmTemplate: _.template('<span class="throbber"></span><select><option value=""><%- placeholder %></option></select><input class="savedcategory" placeholder="<%- textplaceholder %>"><input type="submit" value="<%- save %>"><div class="error"></div>'),

    events: {
        "click": "clicked",
        "submit": "save",
        "mouseout": "mouseout",
        "mouseover": "queueShow",
        "change select": "change"
    },

    mouseout: function() {
        if (!this.$el.find('select, .savedcategory').is(":focus")) {
            this.queueHide(_.bind(this.close, this))
        }
    },

    clicked: function(e) {
        e.stopPropagation()
    },

    initialize: function(options) {
        this.options = options
        this.options.trackHover = false
        this.setElement($('<form class="hover-bubble anchor-left save-selector">').appendTo(this.options.$parent.parent())[0])
        if (r.saved.currentDialog) {
            r.saved.currentDialog.close()
        }
        r.saved.currentDialog = this
        r.ui.Bubble.prototype.initialize.apply(this)
        if (!r.saved.categories) {
            r.saved.categories = new r.saved.SaveCategories()
            this.listenTo(r.saved.categories, 'sync', this.render)
            r.saved.categories.fetch()
        } else {
            this.render()
        }
    },

    close: function() {
        delete r.saved.currentDialog
        this.hide(_.bind(this.remove, this))
    },

    error: function() {
        this.$el.find('select, .savedcategory').attr('disabled', false)
        this.$el.removeClass('working')
        this.$el.find('.error').text(r._('Invalid category name'))
    },

    change: function(e) {
        var input = this.$el.find('.savedcategory')
        var selected = this.$el.find('option:selected').val()
        input.val(selected).focus()
    },

    success: function() {
        r.saved.SaveButton.setSaved(this.options.$parent)
        this.close()
    },

    save: function(e) {
        e.preventDefault()
        var category = this.$el.find('.savedcategory').val()
        this.$el.find('select, .savedcategory').attr('disabled', true)
        this.$el.addClass('working')
        $.request('save',
                  {'id': this.options.$parent.thing_id(), 'category': category},
                  _.bind(this.success, this),
                  undefined, undefined, undefined,
                  _.bind(this.error, this))
    },

    addCategory: function(category) {
        var value = category.get('category')
        this.$el.find('select').append($('<option>').val(value).text(value))
    },

    render: function() {
        this.$el.html(this.confirmTemplate({placeholder: r._('no category'), save: r._('save'), textplaceholder: r._('new category')}))
        r.saved.categories.each(this.addCategory, this)
        this.$el.find('select').first().prop('selected', true)
        this.show()
        this.$el.find('input[type=submit]').focus()
    }
})

r.saved.SaveButton = {
    setSavedFullname: function(fullname) {
        var $button = $('.id-' + fullname).find('.save-button a').first()
        this.setSaved($button)
    },
    request: function($el, type, callback) {
        $.request(type, {'id': $el.thing_id()}, _.bind(callback, this, $el))
    },
    toggleSaved: function($el) {
        if (r.saved.currentDialog) {
            r.saved.currentDialog.close()
        }
        this.isSaved($el) ? this.unsave($el) : this.save($el)
    },
    unsave: function($el) {
        this.request($el, 'unsave', this.setUnsaved)
    },
    save: function($el) {
        if (r.config.gold) {
            (new r.saved.SaveDialog({$parent: $el}))
        } else {
            this.request($el, 'save', this.setSaved)
        }
    },
    isSaved: function($el) {
        return $el.thing().hasClass('saved')
    },
    setUnsaved: function($el) {
        $el.text('save')
        $el.thing().removeClass('saved')
    },
    setSaved: function($el) {
        $el.text('unsave')
        $el.thing().addClass('saved')
    }
}

r.saved.init = function() {
    $('.save-button a').click(function(e) {
        e.stopPropagation()
        e.preventDefault()
        r.saved.SaveButton.toggleSaved($(this))
    })
    $('body').click(function(e) {
        if (r.saved.currentDialog) {
            r.saved.currentDialog.close()
        }
    })
}
