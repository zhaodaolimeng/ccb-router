# 飞书官方样例参考

> 后续修改 bridge 代码时，请比对此文档中的官方样例！

---

## 官方参考链接

1. GitHub Demo: https://github.com/larksuite/oapi-sdk-python-demo
2. 事件处理文档: https://open.feishu.cn/document/server-side-sdk/python--sdk/handle-events

---

## 方式一：长连接接收事件（推荐）

### 官方完整示例

```python
import lark_oapi as lark

def do_p2_im_message_receive_v1(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
    print(f'[ do_p2_im_message_receive_v1 access ], data: {lark.JSON.marshal(data, indent=4)}')

def do_message_event(data: lark.CustomizedEvent) -> None:
    print(f'[ do_customized_event access ], type: message, data: {lark.JSON.marshal(data, indent=4)}')

event_handler = lark.EventDispatcherHandler.builder("", "") \
    .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1) \
    .register_p1_customized_event("这里填入你要自定义订阅的 event 的 key，例如 out_approval", do_message_event) \
    .build()

def main():
    cli = lark.ws.Client("YOUR_APP_ID", "YOUR_APP_SECRET",
                         event_handler=event_handler,
                         log_level=lark.LogLevel.DEBUG)
    cli.start()

if __name__ == "__main__":
    main()
```

### 关键点

- `EventDispatcherHandler.builder("", "")` - 两个参数留空
- 事件处理函数命名: `do_p2_im_message_receive_v1`
- 使用 `lark.ws.Client` 创建 WebSocket 客户端
- 需在 3 秒内处理完事件，否则触发重推

---

## 方式二：Webhook 模式

### 官方 Flask 示例

```python
from flask import Flask
import lark_oapi as lark
from lark_oapi.adapter.flask import *
from lark_oapi.api.im.v1 import *

app = Flask(__name__)

def do_p2_im_message_receive_v1(data: P2ImMessageReceiveV1) -> None:
    print(lark.JSON.marshal(data))

def do_customized_event(data: lark.CustomizedEvent) -> None:
    print(lark.JSON.marshal(data))

handler = lark.EventDispatcherHandler.builder(lark.ENCRYPT_KEY, lark.VERIFICATION_TOKEN, lark.LogLevel.DEBUG) \
    .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1) \
    .register_p1_customized_event("message", do_customized_event) \
    .build()

@app.route("/event", methods=["POST"])
def event():
    resp = handler.do(parse_req())
    return parse_resp(resp)

if __name__ == "__main__":
    app.run(port=7777)
```

---

## 事件数据结构

### Header 中的字段

```json
{
  "schema": "2.0",
  "header": {
    "event_id": "a300e0089df015a4f641f8e7b63ece64",
    "token": "",
    "create_time": "1776385498520",
    "event_type": "im.message.receive_v1",
    "tenant_key": "1b3718d446ce574f",
    "app_id": "cli_a96a5065e9385cc2"
  },
  "event": {
    "sender": {...},
    "message": {...}
  }
}
```

### 去重建议

- **优先使用 `header.event_id`** 去重（每个事件唯一）
- 其次可以用 `message.message_id`
- 时间戳单位是**毫秒**，需除以 1000 得到秒

---

## GitHub Demo 目录结构

```
oapi-sdk-python-demo/
├── composite_api/          # API 组合函数
│   ├── im/
│   │   ├── send_file.py
│   │   └── send_image.py
│   ├── contact/
│   ├── base/
│   └── sheets/
└── quick_start/             # 快速开始示例
    └── robot/               # 机器人自动拉群报警
        └── im.py
```

---

## 对比检查清单

修改 `feishu_ws.py` 时，请检查：

- [ ] 事件处理函数命名是否遵循 `do_p2_xxx` 格式
- [ ] `EventDispatcherHandler.builder("", "")` 参数是否留空
- [ ] 是否用 `header.event_id` 去重
- [ ] 时间戳是否正确处理（毫秒转秒）
- [ ] 事件是否在 3 秒内处理完

