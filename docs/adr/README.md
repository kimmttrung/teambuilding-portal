# Architecture Decision Records

Ghi lại **quyết định nào đã chốt, vì sao, và đánh đổi gì**. Khi đổi ý, không sửa ADR cũ — viết ADR mới và đánh dấu ADR cũ là `Superseded`.

| # | Quyết định | Trạng thái |
|---|---|---|
| [001](001-sqlite-as-primary-database.md) | Dùng SQLite làm CSDL chính | Accepted |
| [002](002-separate-assignment-tables.md) | Tách bảng gán thay vì cột FK trên `registrations` | Accepted |
| [003](003-greedy-allocation-algorithm.md) | Greedy có trọng số cho Auto Allocation | Accepted |
| [004](004-rag-scoped-tools.md) | RAG dùng tool tham số cố định, không text-to-SQL | Accepted |
