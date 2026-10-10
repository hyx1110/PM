import { ElMessageBox } from 'element-plus'

// Confirm the user action, not each HTTP request: one submission may save a
// draft, upload an attachment and then request approval.
let dialogOpen = false

export async function confirmAction(message: string, title = '操作确认', confirmButtonText = '确认提交'): Promise<boolean> {
  if (dialogOpen) return false
  dialogOpen = true
  try {
    await ElMessageBox.confirm(message, title, {
      type: 'warning', confirmButtonText, cancelButtonText: '取消',
      closeOnClickModal: false, closeOnPressEscape: true,
      distinguishCancelAndClose: true, autofocus: false,
      dangerouslyUseHTMLString: false, customClass: 'business-action-confirm',
    })
    return true
  } catch (action) {
    if (action === 'cancel' || action === 'close') return false
    throw action
  } finally { dialogOpen = false }
}

// Reason entry is a form step. Callers still confirm the decision afterwards.
export async function requestActionReason(title: string, message: string): Promise<string | null> {
  if (dialogOpen) return null
  dialogOpen = true
  try {
    const result = await ElMessageBox.prompt(message, title, {
      inputType: 'textarea',
      inputValidator: value => Boolean(value?.trim()) || '请填写原因',
      confirmButtonText: '下一步', cancelButtonText: '取消',
      closeOnClickModal: false, distinguishCancelAndClose: true,
      dangerouslyUseHTMLString: false,
    })
    return result.value.trim()
  } catch (action) {
    if (action === 'cancel' || action === 'close') return null
    throw action
  } finally { dialogOpen = false }
}
