import { describe, expect, it } from 'vitest'
import {
  DIALECT_OPTIONS,
  GENDER_OPTIONS,
  dialectLabel,
  genderLabel,
  validatePassword,
  validateUsername,
} from '../auth'

/** 性别/方言背景选项与标签回显（FR-107）：代码需与后端代码集对齐，纯选填 */
describe('账号资料选项与校验', () => {
  it('性别代码与后端 GENDER_CODES 对齐（male/female/other）', () => {
    expect(GENDER_OPTIONS.map((o) => o.value).sort()).toEqual(['female', 'male', 'other'])
  })

  it('genderLabel 回显标签，未知/空值原样或空串', () => {
    expect(genderLabel('male')).toBe('男')
    expect(genderLabel('female')).toBe('女')
    expect(genderLabel('other')).toBe('其他 / 不便透露')
    expect(genderLabel(null)).toBe('')
    expect(genderLabel('alien')).toBe('alien')
  })

  it('dialectLabel 回显标签，未知/空值原样或空串', () => {
    expect(dialectLabel('yue')).toBe('粤语')
    expect(dialectLabel(null)).toBe('')
    expect(dialectLabel('klingon')).toBe('klingon')
  })

  it('性别与方言选项各自代码无重复（other 在两套枚举中语义独立，允许共存）', () => {
    expect(new Set(GENDER_OPTIONS.map((o) => o.value)).size).toBe(GENDER_OPTIONS.length)
    expect(new Set(DIALECT_OPTIONS.map((o) => o.value)).size).toBe(DIALECT_OPTIONS.length)
  })

  it('用户名与密码校验规则', () => {
    expect(validateUsername('ab')).toContain('3–32')
    expect(validateUsername('学习者_01')).toBeNull()
    expect(validatePassword('1234567')).toContain('8')
    expect(validatePassword('12345678')).toBeNull()
  })
})
