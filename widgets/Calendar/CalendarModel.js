.pragma library

// 生成某年某月的 6×7 = 42 格日历(从周日 SUN 起)。
// month: 0-11。返回 [{n:日数字, muted:是否非本月}]
function buildMonth(year, month) {
    var startDow = new Date(year, month, 1).getDay();          // 0=Sun
    var daysInMonth = new Date(year, month + 1, 0).getDate();
    var daysPrev = new Date(year, month, 0).getDate();
    var cells = [];
    for (var i = 0; i < startDow; i++)
        cells.push({ n: daysPrev - startDow + 1 + i, muted: true });
    for (var d = 1; d <= daysInMonth; d++)
        cells.push({ n: d, muted: false });
    var next = 1;
    while (cells.length < 42)
        cells.push({ n: next++, muted: true });
    return cells;
}

var MONTHS = ["January","February","March","April","May","June",
              "July","August","September","October","November","December"];
var WEEKDAYS_LONG = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];
var WEEKDAYS_SHORT = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];

function monthName(m) { return MONTHS[m]; }
function weekdayLong(d) { return WEEKDAYS_LONG[d]; }
function weekdayShort(d) { return WEEKDAYS_SHORT[d]; }
