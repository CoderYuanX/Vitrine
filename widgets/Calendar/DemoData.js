.pragma library

// 分类色(来自原型设计令牌)
var CAT = {
    work:      "#2f6bff",
    personal:  "#16a34a",
    meeting:   "#7c3aed",
    important: "#d97706",
    holiday:   "#ec4899"
};

var LEGEND = [
    { label: "工作", color: CAT.work },
    { label: "个人", color: CAT.personal },
    { label: "会议", color: CAT.meeting },
    { label: "重要", color: CAT.important },
    { label: "假期", color: CAT.holiday }
];

// 本周(演示)
var TASKS_WEEK = [
    { text: "评审季度预算", date: "本周五" },
    { text: "预订机票",     date: "本周六" }
];

// 天气(演示)
var WEATHER = {
    city: "北京", cityFull: "北京市",
    temp: "18°", desc: "多云", hi: "↑ 21°", lo: "↓ 12°", humidity: "63%"
};

// 效率(演示)
var PRODUCTIVITY = {
    meetings: "3", tasksDone: "5", focus: "6.5h", progress: 0.72,
    note: "进展不错,继续保持!"
};

// 农历 / 笔记(占位,非真实历法)
var LUNAR = { lunarDate: "廿三", label: "丙午年 五月", quote: "“关注进步,\n而非完美。”" };
