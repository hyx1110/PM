import type { OrganizationNode } from '@/types/organization'
import type { UserOption } from '@/types/user'

function descendantOrganizationIds(nodes: OrganizationNode[], selectedIds: Set<number>) {
  const result = new Set(selectedIds)
  const visit = (node: OrganizationNode, inherited: boolean) => {
    const included = inherited || selectedIds.has(node.id)
    if (included) result.add(node.id)
    const children = node.children || []
    children.forEach((child) => visit(child, included))
  }
  nodes.forEach((node) => visit(node, false))
  return result
}

export function resolvePersonnelScopeUserIds(
  scopes: string[],
  users: UserOption[],
  organizations: OrganizationNode[],
): Set<number> | undefined {
  if (!scopes.length) return undefined
  const departmentIds = new Set<number>()
  const organizationIds = new Set<number>()
  const userIds = new Set<number>()
  scopes.forEach((scope) => {
    const [kind, rawId] = scope.split(':')
    const id = Number(rawId)
    if (!id) return
    if (kind === 'department') departmentIds.add(id)
    if (kind === 'organization') organizationIds.add(id)
    if (kind === 'user') userIds.add(id)
  })
  const expandedOrganizationIds = descendantOrganizationIds(organizations, organizationIds)
  return new Set(users
    .filter((user) =>
      userIds.has(user.id)
      || Boolean(user.department_id && departmentIds.has(user.department_id))
      || Boolean(user.organization_id && expandedOrganizationIds.has(user.organization_id)),
    )
    .map((user) => user.id))
}
