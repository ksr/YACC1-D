# md, the Markdown reader

What `md` renders, one example of each (see `man md`). Lines of
prose that follow each other are **one paragraph**, wrapped at 78
columns.

## Lists and quotes

- a bullet item, whose continuation line
  joins the item
- a second item with `code` and a [link](/MAN/MD)

1. a numbered item
2. and another

> a quoted line

## Code and tables

```
dir -R /BIN     a code block: verbatim, indented
```

| command | what it shows |
|---|---|
| md FILE.MD | the file, styled |
| md -p FILE.MD | the same, plain |

---
The end.
