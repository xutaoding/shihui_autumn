define("autumn/0.0.1/autumn",["$"],function(require, exports, module) {
    var $ = require('$');

    var autumn = {};
    //获取cookie 一般用在ajax请求的_xsrf参数上
    autumn.get_cookie = function(name) {
        var r = document.cookie.match("\\b" + name + "=([^;]*)\\b");
        return r ? r[1] : undefined;
    };

    //自动监测字数，超过字数给予警告
    autumn.word_count_monitor = function(selector) {
        $(selector).each(function(){
            var ele = $(this);
            var maxLength = parseInt(ele.attr('data-max-length'));
            var monitor = $('#' + ele.attr('id') + '-wordcount');
            ele.keyup(function (){
                var length =  ele.val().length;
                monitor.text('(' + length + '/' + maxLength + ')');
                monitor.css('color', length > maxLength ? 'red' : 'green');
            });
            ele.keyup();
        });
    };


    return autumn;
});
