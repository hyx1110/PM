<script setup lang="ts">
import { computed } from 'vue'
import type { Department, DepartmentOption, OrganizationNode } from '@/types/organization'
import type { UserOption } from '@/types/user'

interface ScopeOption {
  value: string
  label: string
  children?: ScopeOption[]
}

const props = withDefaults(defineProps<{
  modelValue: string[]
  users: UserOption[]
  departments: Array<Department | DepartmentOption>
  organizations: OrganizationNode[]
  placeholder?: string
  width?: string
}>(), {
  placeholder: '部门 / 组织 / 人员（可多选）',
  width: '320px',
})

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
  change: [value: string[]]
}>()

const cascaderProps = {
  multiple: true,
  checkStrictly: true,
  emitPath: false,
}

const sortedUsers = computed(() => [...props.users].sort((left, right) =>
  left.employee_no.localeCompare(right.employee_no, undefined, { numeric: true, sensitivity: 'base' })
  || left.id - right.id,
))

function organizationOption(node: OrganizationNode): ScopeOption | undefined {
  if (node.status !== 'active') return undefined
  const childOrganizations = (node.children || [])
    .map(organizationOption)
    .filter((item): item is ScopeOption => Boolean(item))
  const people = sortedUsers.value
    .filter((item) => item.organization_id === node.id)
    .map((item) => ({
      value: `user:${item.id}`,
      label: `${item.name}（${item.employee_no}）`,
    }))
  const children = [...childOrganizations, ...people]
  return {
    value: `organization:${node.id}`,
    label: node.name,
    ...(children.length ? { children } : {}),
  }
}

const options = computed<ScopeOption[]>(() => props.departments.map((department) => {
  const organizationChildren = props.organizations
    .filter((node) => node.department_id === department.id)
    .map(organizationOption)
    .filter((item): item is ScopeOption => Boolean(item))
  const unassignedPeople = sortedUsers.value
    .filter((item) => item.department_id === department.id && !item.organization_id)
    .map((item) => ({
      value: `user:${item.id}`,
      label: `${item.name}（${item.employee_no}）`,
    }))
  const children = [...organizationChildren, ...unassignedPeople]
  return {
    value: `department:${department.id}`,
    label: department.name,
    ...(children.length ? { children } : {}),
  }
}))

function update(value: unknown) {
  const normalized = Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : []
  emit('update:modelValue', normalized)
  emit('change', normalized)
}
</script>

<template>
  <el-cascader
    :model-value="modelValue"
    :options="options"
    :props="cascaderProps"
    clearable
    collapse-tags
    collapse-tags-tooltip
    filterable
    :placeholder="placeholder"
    :style="{ width }"
    @update:model-value="update"
  />
</template>
