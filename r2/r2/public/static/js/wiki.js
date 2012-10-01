r.wiki = {
    request: function(req) {
        if (reddit.logged)
            req.data.uh = reddit.modhash;
        $.ajax(req)
    },

    baseApiUrl: function() {
        return r.wiki.baseUrl(true)
    },

    baseUrl: function(api) {
        var base_url = '';
        if (api) {
            base_url += '/api'
        }
        base_url += '/wiki'
        if (!r.config.is_fake) {
            base_url = '/r/' + r.config.post_site + base_url
        }
        return base_url
    },

    init: function() {
        $('body').delegate('.wiki-page .revision_hide', 'click', this.toggleHide)
    },

    toggleHide: function(event) {
        event.preventDefault()
        var $this = $(this),
            url = r.wiki.baseApiUrl() + '/hide',
            $this_parent = $this.parents('.revision')
        $this_parent.toggleClass('hidden')
        r.wiki.request({
            url: url,
            type: 'POST',
            dataType: 'json',
            data: {
                revision: $this.data('revision'),
                page: r.config.wiki_page
            },
            error: function() {
                $this_parent.toggleClass('hidden')
            },
            success: function(data) {
                if (!data.status) {
                    $this_parent.removeClass('hidden')
                } else {
                    $this_parent.addClass('hidden')
                }
            }
        })
    },

    addUser: function(event) {
        event.preventDefault()
        $('#usereditallowerror').hide()
        var $this = $(event.target),
            url = r.wiki.baseApiUrl(true) + '/alloweditor/add'
        r.wiki.request({
            url: url,
            type: 'POST',
            data: {
                username: $this.find('[name="username"]').val(),
                page: r.config.wiki_page
            },
            dataType: 'json',
            error: function() {
                $('#usereditallowerror').show()
            },
            success: function(data) {
                location.reload()
            }
        })
    },

    submitEdit: function(event) {
        event.preventDefault()
        var $this = $(event.target),
            params = {},
            url = r.wiki.baseApiUrl() + '/edit',
            conflict = $('#wiki_edit_conflict'),
            special = $('#wiki_special_error')
        conflict.hide()
        special.hide()
        $.each($this.serializeArray(), function(index,value) {
               params[value.name] = value.value;});
        r.wiki.request({
            url: url,
            type: 'POST',
            dataType: 'json',
            data: params,
            success: function() {
                window.location = r.wiki.baseUrl() + '/' + r.config.wiki_page
            },
            statusCode: {
                409: function(xhr) {
                    var info = JSON.parse(xhr.responseText)
                        ,content = $this.children('#content')
                    conflict.children('#youredit').val(content.val())
                    conflict.children('#yourdiff').html(info.diffcontent)
                    $this.children('#previous').val(info.newrevision)
                    content.val(info.newcontent)
                    conflict.fadeIn('slow')
                },
                415: function(xhr) {
                    var errors = JSON.parse(xhr.responseText).special_errors
                        ,specials = special.children('#specials')
                    specials.empty()
                    for(i in errors) {
                        specials.append(errors[i]+'<br/>')
                    }
                    special.fadeIn('slow')
                },
                429: function(xhr) {
                    var message = JSON.parse(xhr.responseText).message
                        ,specials = special.children('#specials')
                    specials.empty()
                    specials.text(message)
                    special.fadeIn('slow')
                }
            }
        })
    },

    goCompare: function() {
        v1 = $('input:radio[name=v1]:checked').val()
        v2 = $('input:radio[name=v2]:checked').val()
        url = r.wiki.baseUrl() + '/' + r.config.wiki_page + '?v=' + v1
        if (v2 != v1) {
            url += '&v2=' + v2
        }
        window.location = url
    }
}
