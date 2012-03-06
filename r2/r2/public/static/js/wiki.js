$(function() {
    function WikiToggleHide() {
        var jthis = $(this)
        var url = jthis.data("baseurl") + "/api/hide/" + jthis.data("revision") + "/" + jthis.data("page")
        $.ajax({
            url: url,
            type: 'POST',
            dataType: 'json',
            success: function(data) {
                if(!data.status) {
                    jthis.parent().removeClass("hidden")
                } else {
                    jthis.parent().addClass("hidden")
                }
            }
        })
    }
    $(".wiki .revision_hide").click(WikiToggleHide)
    
    function WikiSubmitEdit(event) {
        event.preventDefault()
        var jthis = $(this)
        var url = jthis.data("baseurl") + "/api/edit/" + jthis.data("page")
        var conflict = $(".wiki #conflict");
        var special = $(".wiki #special");
        conflict.hide();
        special.hide()
        $.ajax({
            url: url,
            type: 'POST',
            dataType: 'json',
            data: jthis.serialize(),
            success: function() {
                window.location = jthis.data("baseurl") + "/" + jthis.data("page");
            },
            statusCode: {
                409: function(xhr) {
                    var info = jQuery.parseJSON(xhr.responseText)
                    var content = jthis.children("#content");
                    conflict.children("#youredit").val(content.val())
                    conflict.children("#yourdiff").html(info.diffcontent)
                    jthis.children("#previous").val(info.newrevision)
                    content.val(info.newcontent)
                    conflict.fadeIn('slow')
                },
                415: function(xhr) {
                    var errors = jQuery.parseJSON(xhr.responseText).special_errors;
                    var specials = special.children("#specials")
                    specials.html("");
                    for(i in errors) {
                        specials.append(errors[i]+"<br/>")
                    }
                    special.fadeIn('slow');
                }
            }
        })
    }
    $(".wiki #editform").submit(WikiSubmitEdit)
})

