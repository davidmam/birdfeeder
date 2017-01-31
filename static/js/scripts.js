var API_URL = 'http://192.168.0.3:8000/bird-details'

function recordBird() {
    $.ajax({ url: API_URL,
            type: "POST",
            data: $("#birdform").serialize()
    });
}

$(document).ready(function(){
    $("#submit").click(function(event){
        recordBird();
    })
})
