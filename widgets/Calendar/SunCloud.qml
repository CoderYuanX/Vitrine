import QtQuick

// 太阳+云图标(复刻原型 viewBox 64×52:太阳 #f7b733 圆 + 浅灰云)
Canvas {
    id: root
    property color sun: "#f7b733"
    property color cloud: "#eef1f6"
    property color cloudStroke: "#d9dfea"
    implicitWidth: 64
    implicitHeight: 52
    onPaint: {
        var ctx = getContext("2d");
        ctx.reset();
        ctx.save();
        ctx.scale(width / 64, height / 52);
        // 太阳
        ctx.fillStyle = root.sun;
        ctx.beginPath();
        ctx.arc(23, 20, 11, 0, 2 * Math.PI);
        ctx.fill();
        // 云(几个圆 + 底座近似原型轮廓)
        ctx.fillStyle = root.cloud;
        ctx.strokeStyle = root.cloudStroke;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(31, 30, 13, Math.PI, 2 * Math.PI);
        ctx.arc(43, 33, 10, Math.PI * 1.5, 2 * Math.PI);
        ctx.arc(22, 34, 9, Math.PI * 0.5, Math.PI * 1.5, true);
        ctx.lineTo(16, 44);
        ctx.lineTo(46, 44);
        ctx.arc(43, 34, 10, 0, Math.PI * 0.5);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        ctx.restore();
    }
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
}
