import { type TFunction } from 'i18next'
import {
  LayoutDashboard,
  Monitor,
  ListTodo,
  HelpCircle,
  Bell,
  Palette,
  Settings,
  Wrench,
  UserCog,
  Users,
  Command,
  GalleryVerticalEnd,
  Briefcase,
} from 'lucide-react'
import { type NavGroup, type Team, type User } from '../types'

/** 侧边栏占位用户：会话尚未建立或接口未返回时使用。 */
export const sidebarUser: User = {
  name: 'User',
  email: 'user@example.com',
}

/** 侧边栏团队列表（演示数据，不随语言变化）。 */
export const sidebarTeams: Team[] = [
  {
    name: 'Zata Admin',
    logo: Command,
    plan: 'Vite + ShadcnUI',
  },
  {
    name: 'Acme Inc',
    logo: GalleryVerticalEnd,
    plan: 'Enterprise',
  },
]

/**
 * 构造随语言变化的侧边栏导航分组。
 *
 * 标题不再写死在数据里，而是通过 i18next 的 `t` 读取 `nav` 命名空间，因此语言
 * 切换后侧边栏会随组件重渲染一起更新。调用方每次渲染都重新构造即可——这里只是
 * 组装对象字面量，没有需要缓存的昂贵计算。
 *
 * @param t - i18next 翻译函数（默认命名空间为 `translation`）。
 * @returns 已按当前语言翻译的导航分组。
 */
export function createNavGroups(t: TFunction): NavGroup[] {
  return [
    {
      title: t('nav.general'),
      items: [
        {
          title: t('nav.dashboard'),
          url: '/',
          icon: LayoutDashboard,
        },
        {
          title: t('nav.projects'),
          url: '/projects',
          icon: Briefcase,
        },
        {
          title: t('nav.tasks'),
          url: '/tasks',
          icon: ListTodo,
        },
        {
          title: t('nav.users'),
          url: '/users',
          icon: Users,
        },
      ],
    },
    {
      title: t('nav.other'),
      items: [
        {
          title: t('nav.settings'),
          icon: Settings,
          items: [
            {
              title: t('nav.profile'),
              url: '/settings',
              icon: UserCog,
            },
            {
              title: t('nav.account'),
              url: '/settings/account',
              icon: Wrench,
            },
            {
              title: t('nav.appearance'),
              url: '/settings/appearance',
              icon: Palette,
            },
            {
              title: t('nav.notifications'),
              url: '/settings/notifications',
              icon: Bell,
            },
            {
              title: t('nav.display'),
              url: '/settings/display',
              icon: Monitor,
            },
          ],
        },
        {
          title: t('nav.helpCenter'),
          url: '/help-center',
          icon: HelpCircle,
        },
      ],
    },
  ]
}
