# Z.AI Key Monitor

Web application giám sát API key Z.AI - kiểm tra xác thực, level, quota và thời gian reset theo thời gian thực.

<img width="1901" height="908" alt="image" src="https://github.com/user-attachments/assets/0ab6d024-1618-4953-856f-e96310c92634" />

## Tính năng

- **Thêm key đơn hoặc theo list** - Nhập 1 key hoặc nhiều key cùng lúc (cách nhau bởi dòng mới, dấu phẩy, chấm phẩy)
- **Kiểm tra xác thực** - Xác định key hợp lệ / không hợp lệ / lỗi
- **Hiển thị level** - Lite, Pro, Max, Enterprise...
- **Quota realtime** - Đã dùng / Tổng số / Còn lại kèm thanh tiến trình màu
- **Chi tiết theo model** - `search-prime`, `web-reader`, `zread`...
- **Thời gian reset** - `nextResetTime` với countdown ngược
- **Lưu SQLite** - Dữ liệu persists trong file `keys.db`, không mất khi restart
- **Tìm kiếm/filter** key nhanh
- **Auto-refresh** mỗi 30 giây

## Cài đặt

```bash
pip install flask requests
```

## Chạy

```bash
python app.py
```

Truy cập: `http://localhost:5000`

## Cấu trúc

```
├── app.py              # Backend Flask + SQLite
├── keys.db             # SQLite database (tự tạo)
├── templates/
│   └── index.html      # Giao diện web
├── requirements.txt    # Dependencies
└── README.md
```

## API Endpoints

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/` | Giao diện web |
| GET | `/api/keys?search=` | Lấy danh sách key |
| POST | `/api/keys` | Thêm key (`{key: "..."}` hoặc `{keys: "key1,key2..."}`) |
| DELETE | `/api/keys/<key>` | Xóa 1 key |
| POST | `/api/keys/clear` | Xóa tất cả key |
| POST | `/api/validate/<key>` | Kiểm tra 1 key |
| POST | `/api/validate-all` | Kiểm tra tất cả key |
| GET | `/api/stats` | Thống kê (tổng, hợp lệ, lỗi...) |

## Dữ liệu trả về từ API

```json
{
  "code": 200,
  "data": {
    "level": "lite",
    "limits": [
      {
        "type": "TIME_LIMIT",
        "usage": 100,
        "currentValue": 12,
        "remaining": 88,
        "percentage": 12,
        "nextResetTime": 1777694756997,
        "usageDetails": [
          {"modelCode": "search-prime", "usage": 12},
          {"modelCode": "web-reader", "usage": 0}
        ]
      }
    ]
  }
}
```
