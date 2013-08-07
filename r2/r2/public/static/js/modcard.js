r.modcard = {}

r.modcard.modcards = {}

r.modcard.user_type_strings = {
    regular: r._('regular user'),
    banned: r._('banned user'),
    moderator: r._('moderator'),
    invited_moderator: r._('invited moderator'),
    contributor: r._('approved submitter')
}

/* TODO: Write a babel extractor for underscore templates */
r.modcard.i18n = {
    change: r._('change'),
    inyoursubreddit: r._('in your subreddit'),
    linkkarma: r._('link karma'),
    subredditkarma: r._('subreddit karma'),
    notes: r._('notes'),
    info: r._('info'),
    back: r._('back'),
    next: r._('next')
}

r.modcard.UserInfo = Backbone.Model.extend({
    parse: function(response, options) {
        return response.userinfo
    },
    url: function() {
        return '/r/' + this.get('subreddit') + '/api/userinfo.json?user=' + this.get('username')
    }
})

r.modcard.UserInfoView = Backbone.View.extend({
    initialize: function() {
        this.model = new r.modcard.UserInfo(this.options)
        this.model.on('sync', this.render, this)
        this.model.fetch()
    },
    render: function() {
        var data = this.model.attributes
        data.user_type_str = r.modcard.user_type_strings[data.user_type]
        data._ = r.modcard.i18n
        this.$el.empty().html(
            r.templates.make('templates/modcard-info',
                             this.model.attributes)
        )
        return this
    }
})

r.modcard.ModCard = Backbone.View.extend({
    events: {
        'click .quit': 'quitclicked',
        'click': 'clicked',
        'click .flipper': 'flipclicked'
    },
    initialize: function() {
        $('html').on('click', _.bind(this.hide, this))
    },
    flipclicked: function(e) {
        e.preventDefault()
        this.flip()
    },
    quitclicked: function(e) {
        e.preventDefault()
        this.hide()
    },
    clicked: function(e) {e.stopPropagation()},
    render: function() {
        this.$el.data('modcard', this)
        this.$el.addClass('flippable modcard')
        var data = this.options
        data._ = r.modcard.i18n
        this.$el.html(r.templates.make('templates/modcard', data))
        this.infoview = new r.modcard.UserInfoView({
            el: this.$el.find('.modcard-info')[0],
            username: this.options.username,
            subreddit: this.options.subreddit
        })
        return this
    },
    isvisible: function() {
        return this.$el.is(':visible')
    },
    isflipped: function() {
        return this.$el.hasClass('flipped')
    },
    hide: function() {
        this.$el.hide(80)
        return this
    },
    front: function() {
        this.$el.removeClass('flipped')
        return this
    },
    back: function() {
        this.$el.addClass('flipped')
        return this
    },
    show: function(x, y) {
        // admin bar offset
        var offset_y = $('body').css('margin-top').replace('px', '')
        this.$el.css('top', y - offset_y)
        this.$el.css('left', x)
        this.$el.show(40)
        return this
    },
    flip: function() {
        if(this.isflipped()) {
            this.front()
        } else {
            this.back()
        }
        return this
    }
})

r.modcard.ModCarder = Backbone.View.extend({
    events: {
        'click': 'expandclicked'
    },
    initialize: function() {
        this.username = this.$el.data('username'),
        this.subreddit = this.$el.data('subreddit')
    },
    expandclicked: function(e) {
        e.preventDefault()
        e.stopPropagation()
        this.expand(e.pageX, e.pageY)
    },
    expand: function(x, y) {
        if(!this.modcard) {
            this.init()
        }
        this.modcard.show(x, y)
    },
    init: function() {
        var name = this.subreddit + '/' + this.username
        var modcard = r.modcard.modcards[name]
        if(modcard) {
            this.modcard = modcard
        } else {
            var $modcard = $('<div>');
            this.modcard = this.create($modcard)
            $modcard.insertAfter(this.$el)
            r.modcard.modcards[name] = this.modcard
        }
        return this
    },
    create: function(el) {
        return new r.modcard.ModCard({
            el: el,
            username: this.username,
            subreddit: this.subreddit
        }).render()
    }
})

$(function() {
    $('.modcarder').each(function(idx, el) {
        $(el).data('ModCarder', new r.modcard.ModCarder({el: el}))
    })
})
