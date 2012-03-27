$(function() {
    function WikiToggleHide(event) {
        event.preventDefault()
        var $this = $(this)
            ,url = $this.data("baseurl") + "/api/hide/" + $this.data("revision") + "/" + $this.data("page")
            ,$this_parent = $this.parents(".revision");
        $this_parent.toggleClass("hidden")
        $.ajax({
            url: url,
            type: 'POST',
            dataType: 'json',
            error: function() {
                $this_parent.toggleClass("hidden")
            },
            success: function(data) {
                if(!data.status) {
                    $this_parent.removeClass("hidden")
                } else {
                    $this_parent.addClass("hidden")
                }
            }
        })
    }
    $("body").delegate(".wiki .revision_hide", "click", WikiToggleHide)
    
    function WikiSubmitEdit(event) {
        event.preventDefault()
        var $this = $(this)
            ,url = $this.data("baseurl") + "/api/edit/" + $this.data("page")
            ,conflict = $(".wiki #conflict")
            ,special = $(".wiki #special")
        conflict.hide()
        special.hide()
        $.ajax({
            url: url,
            type: 'POST',
            dataType: 'json',
            data: $this.serialize(),
            success: function() {
                window.location = $this.data("baseurl") + "/" + $this.data("page")
            },
            statusCode: {
                409: function(xhr) {
                    var info = JSON.parse(xhr.responseText)
                        ,content = $this.children("#content")
                    conflict.children("#youredit").val(content.val())
                    conflict.children("#yourdiff").html(info.diffcontent)
                    $this.children("#previous").val(info.newrevision)
                    content.val(info.newcontent)
                    conflict.fadeIn('slow')
                },
                415: function(xhr) {
                    var errors = JSON.parse(xhr.responseText).special_errors
                        ,specials = special.children("#specials")
                    specials.empty()
                    for(i in errors) {
                        specials.append(errors[i]+"<br/>")
                    }
                    special.fadeIn('slow')
                }
            }
        })
    }
    $("body").delegate(".wiki #editform", "submit", WikiSubmitEdit)
})

function ReloadPage() {location.reload()}
