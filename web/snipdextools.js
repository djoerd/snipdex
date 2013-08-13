function posturl(url) {
    // turns an http-get url into an http-post request

    var components;
    if (url.match('\\?')) {
      components  = url.split('?');
    }
    else {
      components = [ url ];
    }
    var form = document.createElement("form");
    form.setAttribute("method", "post");
    form.setAttribute("action", components[0]);
    form.snipdexsubmit = form.submit;

    var params;
    if (url.match('\\?')) {
      if (components[1].match('&')) {
        params = components[1].split('&');
      }
      else {
        params = [ components[1] ]
      }
      for(var param in params) {
        var keyvalue = params[param].split('=')
        var hiddenField = document.createElement("input");
        hiddenField.setAttribute("type", "hidden");
        hiddenField.setAttribute("name", keyvalue[0]);
        hiddenField.setAttribute("value", keyvalue[1]);
        form.appendChild(hiddenField);
      }
    }

    document.body.appendChild(form);
    form.snipdexsubmit();
}

