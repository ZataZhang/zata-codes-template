import { type SVGProps } from 'react'
import { cn } from '@/lib/utils'

/** 渲染平台通用标识。 */
export function Logo({ className, ...props }: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox='0 0 24 24'
      xmlns='http://www.w3.org/2000/svg'
      height='24'
      width='24'
      fill='none'
      stroke='currentColor'
      strokeWidth='2'
      strokeLinecap='round'
      strokeLinejoin='round'
      className={cn('size-6', className)}
      {...props}
    >
      <title>Agent Platform</title>
      <circle cx='12' cy='5.5' r='2.5' />
      <circle cx='5.5' cy='18' r='2.5' />
      <circle cx='18.5' cy='18' r='2.5' />
      <path d='m10.5 7.5-3.7 8M13.5 7.5l3.7 8M8 18h8' />
    </svg>
  )
}
