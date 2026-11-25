"use client"

import { useEffect, useState, type ClipboardEvent, type ReactNode } from "react"
import Image from "next/image"
import { Dialog } from "@base-ui/react/dialog"
import { Tabs } from "@base-ui/react/tabs"
import { FileSpreadsheet, Image as ImageIcon, Paperclip, X } from "lucide-react"
import { cn } from "@/lib/utils"

const SPREADSHEET_EXTENSIONS = new Set([".xlsx", ".xls", ".csv"])
const SPREADSHEET_PREVIEW_ROWS = 50
const SPREADSHEET_PREVIEW_COLUMNS = 20

function SpreadsheetPreviewRows({ rows }: { rows: string[][] }) {
  return (
    <tbody>
      {rows.map((row, rowIndex) => (
        <tr
          key={rowIndex}
          className="first:bg-muted first:font-semibold odd:bg-muted/70"
        >
          {row.map((cell, columnIndex) => (
            <td
              key={columnIndex}
              className="truncate border-r border-b px-1"
              title={cell}
            >
              {cell}
            </td>
          ))}
        </tr>
      ))}
    </tbody>
  )
}

function SpreadsheetPreview({ file }: { file: File }) {
  const [selection, setSelection] = useState<{ file: File; index: number }>()
  const [preview, setPreview] = useState<{
    file: File
    sheetIndex: number
    sheetNames: string[]
    thumbnailRows: string[][]
    rows: string[][]
  }>()
  const sheetIndex = selection?.file === file ? selection.index : 0

  useEffect(() => {
    let active = true
    async function loadPreview() {
      try {
        const [{ read, utils }, contents] = await Promise.all([
          import("xlsx"),
          file.arrayBuffer(),
        ])
        if (!active) return
        const workbook = read(contents, {
          sheets: sheetIndex,
          sheetRows: SPREADSHEET_PREVIEW_ROWS,
          raw: true,
          cellHTML: false,
          cellFormula: false,
        })
        const sheet = workbook.Sheets[workbook.SheetNames[sheetIndex]]
        const bounds = sheet?.["!ref"]
          ? utils.decode_range(sheet["!ref"])
          : null
        const rows = bounds
          ? utils.sheet_to_json<string[]>(sheet, {
              header: 1,
              raw: false,
              defval: "",
              range: {
                s: { r: 0, c: 0 },
                e: {
                  r: Math.min(bounds.e.r, SPREADSHEET_PREVIEW_ROWS - 1),
                  c: Math.min(bounds.e.c, SPREADSHEET_PREVIEW_COLUMNS - 1),
                },
              },
            })
          : []
        setPreview((previous) => ({
          file,
          sheetIndex,
          sheetNames: workbook.SheetNames,
          thumbnailRows:
            sheetIndex === 0
              ? rows.slice(0, 4).map((row) => row.slice(0, 3))
              : (previous?.thumbnailRows ?? []),
          rows: rows.some((row) => row.some(Boolean)) ? rows : [],
        }))
      } catch {
        if (active) {
          setPreview((previous) => ({
            file,
            sheetIndex,
            sheetNames: previous?.file === file ? previous.sheetNames : [],
            thumbnailRows:
              previous?.file === file ? previous.thumbnailRows : [],
            rows: [],
          }))
        }
      }
    }
    void loadPreview()
    return () => {
      active = false
    }
  }, [file, sheetIndex])

  const workbookPreview = preview?.file === file ? preview : undefined
  const thumbnailRows = workbookPreview?.thumbnailRows
  const rows =
    workbookPreview?.sheetIndex === sheetIndex
      ? workbookPreview.rows
      : undefined

  return (
    <Dialog.Root>
      <div className="relative flex size-24 flex-col overflow-hidden rounded-xl">
        <div className="flex min-h-0 flex-1 items-start overflow-hidden bg-background">
          {thumbnailRows?.some((row) => row.some(Boolean)) ? (
            <table
              aria-label={`Spreadsheet thumbnail for ${file.name}`}
              className="w-full table-fixed border-collapse text-[8px] leading-4"
            >
              <SpreadsheetPreviewRows rows={thumbnailRows} />
            </table>
          ) : (
            <span className="m-auto text-[10px] text-muted-foreground">
              {workbookPreview ? "Preview unavailable" : "Loading…"}
            </span>
          )}
        </div>
        <div
          className="flex h-7 shrink-0 items-center gap-1 border-t pr-7 pl-1.5 text-[10px]"
          title={file.name}
        >
          <FileSpreadsheet className="size-3 shrink-0 text-emerald-600" />
          <span className="truncate">{file.name}</span>
        </div>
        {workbookPreview?.sheetNames.length ? (
          <Dialog.Trigger
            type="button"
            aria-label={`Preview ${file.name}`}
            className="absolute inset-0 cursor-zoom-in rounded-xl focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"
          />
        ) : null}
      </div>
      <PreviewPopup className="max-w-5xl">
        <Dialog.Title className="min-w-0 truncate pr-10">
          {file.name}
        </Dialog.Title>
        <Dialog.Description>
          Up to {SPREADSHEET_PREVIEW_ROWS} rows and{" "}
          {SPREADSHEET_PREVIEW_COLUMNS} columns per sheet.
        </Dialog.Description>
        <Tabs.Root
          className="min-w-0 overflow-hidden rounded-md border"
          value={sheetIndex}
          onValueChange={(index) => setSelection({ file, index })}
        >
          <Tabs.Panel
            key={sheetIndex}
            value={sheetIndex}
            className="h-[55dvh] overflow-auto"
            tabIndex={0}
          >
            {rows?.length ? (
              <table className="w-max min-w-full border-collapse text-sm [&_td]:max-w-80 [&_td]:px-3 [&_td]:py-1.5">
                <SpreadsheetPreviewRows rows={rows} />
              </table>
            ) : (
              <p role="status" className="p-3 text-sm text-muted-foreground">
                {rows ? "No cells to preview" : "Loading…"}
              </p>
            )}
          </Tabs.Panel>
          <Tabs.List
            aria-label="Worksheets"
            className="flex gap-1 overflow-x-auto border-t bg-muted/50 px-2 pb-1"
          >
            {workbookPreview?.sheetNames.map((sheetName, index) => (
              <Tabs.Tab
                key={sheetName}
                value={index}
                className="shrink-0 rounded-b-md px-3 py-2 text-sm whitespace-nowrap text-muted-foreground hover:bg-muted focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring data-active:bg-background data-active:font-semibold data-active:text-foreground data-active:shadow-sm"
              >
                {sheetName}
              </Tabs.Tab>
            ))}
          </Tabs.List>
        </Tabs.Root>
      </PreviewPopup>
    </Dialog.Root>
  )
}

function ImagePreview({ file }: { file: File }) {
  const [preview, setPreview] = useState<{ file: File; url: string }>()

  useEffect(() => {
    const url = URL.createObjectURL(file)
    setPreview({ file, url })
    return () => URL.revokeObjectURL(url)
  }, [file])

  if (preview?.file !== file) return null

  return (
    <Dialog.Root>
      <Dialog.Trigger
        type="button"
        aria-label={`Preview ${file.name}`}
        className="relative block size-24 cursor-zoom-in overflow-hidden rounded-xl focus-visible:outline-2 focus-visible:outline-ring"
      >
        <ImageIcon className="absolute inset-0 m-auto size-5 text-muted-foreground" />
        <Image
          src={preview.url}
          alt=""
          fill
          unoptimized
          className="object-cover"
        />
      </Dialog.Trigger>
      <PreviewPopup className="max-w-4xl">
        <Dialog.Title className="min-w-0 truncate pr-10">
          {file.name}
        </Dialog.Title>
        <Dialog.Description className="sr-only">
          Full image preview
        </Dialog.Description>
        <div className="relative h-[70dvh]">
          <Image
            src={preview.url}
            alt={file.name}
            fill
            unoptimized
            className="object-contain"
          />
        </div>
      </PreviewPopup>
    </Dialog.Root>
  )
}

function PreviewPopup({
  className,
  children,
}: {
  className: string
  children: ReactNode
}) {
  return (
    <Dialog.Portal>
      <Dialog.Backdrop className="fixed inset-0 z-50 bg-black/60" />
      <Dialog.Popup
        className={cn(
          "fixed top-1/2 left-1/2 z-50 grid w-[calc(100%-2rem)] -translate-x-1/2 -translate-y-1/2 gap-4 rounded-xl border bg-background p-4 shadow-lg sm:p-6",
          className
        )}
      >
        {children}
        <Dialog.Close
          type="button"
          aria-label="Close preview"
          className="absolute top-3 right-3 inline-flex size-8 items-center justify-center rounded-md hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring"
        >
          <X className="size-4" />
        </Dialog.Close>
      </Dialog.Popup>
    </Dialog.Portal>
  )
}

/** 从粘贴事件接收文件；纯文本继续交由浏览器处理。 */
export function takePastedFiles(event: ClipboardEvent): File[] {
  const files = Array.from(event.clipboardData.files)
  if (files.length > 0) event.preventDefault()
  return files
}

/** 在发送前展示本地附件。调用方负责附件校验、移除和上传。 */
export function LocalAttachmentPreview({ file }: { file: File }) {
  const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase()
  if (SPREADSHEET_EXTENSIONS.has(extension))
    return <SpreadsheetPreview file={file} />
  if ([".png", ".jpg", ".jpeg"].includes(extension))
    return <ImagePreview file={file} />
  return (
    <span className="flex min-w-0 items-center gap-2 rounded-md border px-2 py-1.5 text-xs">
      <Paperclip aria-hidden="true" className="size-4 shrink-0" />
      <span className="truncate" title={file.name}>
        {file.name}
      </span>
    </span>
  )
}
