var API_URL = 'http://192.168.0.3:8000/bird-details'

function recordBird() {
    $.post({ url: API_URL,
            data: $("#birdform").serialise()
    });
}

$().ready(function(){
    $("#submit").click(function(){
        recordBird();
    })
})
