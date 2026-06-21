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
    { label: "Work",      color: CAT.work },
    { label: "Personal",  color: CAT.personal },
    { label: "Meeting",   color: CAT.meeting },
    { label: "Important", color: CAT.important },
    { label: "Holiday",   color: CAT.holiday }
];

// 按"月内第 n 天"映射圆点颜色,复刻原型的彩色分布,使任意真实月份都有相似观感。
var W = CAT.work, P = CAT.personal, M = CAT.meeting, I = CAT.important, H = CAT.holiday;
var DOT_BY_DAY = {
    1:H, 2:M, 3:M, 4:M, 5:W, 6:W, 8:I, 9:I, 10:W, 11:W,
    13:M, 14:I, 15:W, 16:I, 19:P, 26:M, 27:M, 28:I, 29:H
};
function dotFor(day) { return DOT_BY_DAY[day] || ""; }

// 任务(演示)。done 在运行时由 ListModel 维护。
var TASKS_TODAY = [
    { text: "Prepare project proposal", tag: "Work",     tc: "#7c3aed", tb: "rgba(124,58,237,.12)" },
    { text: "Reply to client emails",   tag: "Work",     tc: "#7c3aed", tb: "rgba(124,58,237,.12)" },
    { text: "Buy groceries for dinner", tag: "Personal", tc: "#16a34a", tb: "rgba(22,163,74,.12)" }
];
var TASKS_WEEK = [
    { text: "Review Q2 budget",    date: "May 22" },
    { text: "Book flight tickets", date: "May 23" }
];

// 今日日程(演示)
var AGENDA = [
    { time: "09:00 AM", dur: "30m", title: "Daily Standup",      tag: "Meeting",  color: CAT.work,    place: "Meet" },
    { time: "10:00 AM", dur: "1h",  title: "Project Review",     tag: "Work",     color: CAT.meeting, place: "Office 3A" },
    { time: "12:00 PM", dur: "1h",  title: "Lunch with Sarah",   tag: "Personal", color: CAT.personal,place: "Cafe de la Presse" },
    { time: "02:00 PM", dur: "2h",  title: "Design System Sync", tag: "Meeting",  color: CAT.work,    place: "Meet" },
    { time: "04:30 PM", dur: "30m", title: "Admin Catch-up",     tag: "Important",color: CAT.important,place: "Office 3A" }
];
function tagColor(tag) {
    return tag === "Work" ? "#7c3aed"
         : tag === "Personal" ? "#16a34a"
         : tag === "Important" ? "#d97706"
         : "#2f6bff";  // Meeting / 默认
}
function tagBg(tag) {
    return tag === "Work" ? "rgba(124,58,237,.12)"
         : tag === "Personal" ? "rgba(22,163,74,.12)"
         : tag === "Important" ? "rgba(217,119,6,.12)"
         : "rgba(47,107,255,.12)";
}

// 即将到来(演示)
var UPCOMING = [
    { title: "Design Review",     when: "May 22, 11:00 AM" },
    { title: "Marketing Sync",    when: "May 23, 09:30 AM" },
    { title: "Quarterly Planning",when: "May 26, 02:00 PM" }
];

// 天气(演示)
var WEATHER = {
    city: "San Francisco", cityFull: "San Francisco, CA",
    temp: "18°", desc: "Partly Cloudy", hi: "↑ 21°", lo: "↓ 12°", humidity: "63%"
};

// 效率(演示)
var PRODUCTIVITY = {
    meetings: "3", tasksDone: "5", focus: "6.5h", progress: 0.72,
    note: "Great progress! Keep it up."
};

// 农历 / 笔记(占位,非真实历法)
var LUNAR = { lunarDate: "23", label: "Shawwal 1446", quote: "“Focus on progress,\nnot perfection.”" };
