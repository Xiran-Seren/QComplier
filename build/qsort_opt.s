.arch armv8-a
.section .bss
.align 3
.global a
a:
    .zero 80
.section .text
.global _start
swap:
    stp x29, x30, [sp, #-16]!
    mov x29, sp
    sub sp, sp, #112
    str x0, [x29, #-8]
    str x1, [x29, #-16]
    str x2, [x29, #-24]
    ldr x9, [x29, #-16]
    mov x10, #8
    mul x11, x9, x10
    str x11, [x29, #-32]
    ldr x9, [x29, #-8]
    ldr x10, [x29, #-32]
    add x11, x9, x10
    str x11, [x29, #-40]
    ldr x9, [x29, #-40]
    ldr x10, [x9]
    str x10, [x29, #-48]
    ldr x9, [x29, #-48]
    str x9, [x29, #-112]
    ldr x9, [x29, #-24]
    mov x10, #8
    mul x11, x9, x10
    str x11, [x29, #-56]
    ldr x9, [x29, #-8]
    ldr x10, [x29, #-56]
    add x11, x9, x10
    str x11, [x29, #-64]
    ldr x9, [x29, #-64]
    ldr x10, [x9]
    str x10, [x29, #-72]
    ldr x9, [x29, #-16]
    mov x10, #8
    mul x11, x9, x10
    str x11, [x29, #-80]
    ldr x9, [x29, #-8]
    ldr x10, [x29, #-80]
    add x11, x9, x10
    str x11, [x29, #-88]
    ldr x9, [x29, #-88]
    ldr x10, [x29, #-72]
    str x10, [x9]
    ldr x9, [x29, #-24]
    mov x10, #8
    mul x11, x9, x10
    str x11, [x29, #-96]
    ldr x9, [x29, #-8]
    ldr x10, [x29, #-96]
    add x11, x9, x10
    str x11, [x29, #-104]
    ldr x9, [x29, #-104]
    ldr x10, [x29, #-112]
    str x10, [x9]
    mov x0, #0
    b .Lswap_exit
.Lswap_exit:
    add sp, sp, #112
    ldp x29, x30, [sp], #16
    ret
partition:
    stp x29, x30, [sp, #-16]!
    mov x29, sp
    sub sp, sp, #160
    str x0, [x29, #-8]
    str x1, [x29, #-40]
    str x2, [x29, #-16]
    ldr x9, [x29, #-16]
    mov x10, #8
    mul x11, x9, x10
    str x11, [x29, #-56]
    ldr x9, [x29, #-8]
    ldr x10, [x29, #-56]
    add x11, x9, x10
    str x11, [x29, #-64]
    ldr x9, [x29, #-64]
    ldr x10, [x9]
    str x10, [x29, #-72]
    ldr x9, [x29, #-72]
    str x9, [x29, #-48]
    ldr x9, [x29, #-40]
    mov x10, #1
    sub x11, x9, x10
    str x11, [x29, #-80]
    ldr x9, [x29, #-80]
    str x9, [x29, #-24]
    ldr x9, [x29, #-40]
    mov x10, #1
    sub x11, x9, x10
    str x11, [x29, #-88]
    ldr x9, [x29, #-88]
    str x9, [x29, #-32]
l0:
    ldr x9, [x29, #-32]
    mov x10, #1
    add x11, x9, x10
    str x11, [x29, #-96]
    ldr x9, [x29, #-96]
    str x9, [x29, #-32]
    ldr x9, [x29, #-96]
    ldr x10, [x29, #-16]
    cmp x9, x10
    b.lt l2
    b l1
l2:
    ldr x9, [x29, #-32]
    mov x10, #8
    mul x11, x9, x10
    str x11, [x29, #-104]
    ldr x9, [x29, #-8]
    ldr x10, [x29, #-104]
    add x11, x9, x10
    str x11, [x29, #-112]
    ldr x9, [x29, #-112]
    ldr x10, [x9]
    str x10, [x29, #-120]
    ldr x9, [x29, #-120]
    ldr x10, [x29, #-48]
    cmp x9, x10
    b.lt l5
    b l3
l5:
    ldr x9, [x29, #-24]
    mov x10, #1
    add x11, x9, x10
    str x11, [x29, #-128]
    ldr x9, [x29, #-128]
    str x9, [x29, #-24]
    ldr x9, [x29, #-8]
    mov x0, x9
    ldr x9, [x29, #-24]
    mov x1, x9
    ldr x9, [x29, #-32]
    mov x2, x9
    bl swap
    str x0, [x29, #-136]
l3:
    b l0
l1:
    ldr x9, [x29, #-24]
    mov x10, #1
    add x11, x9, x10
    str x11, [x29, #-144]
    ldr x9, [x29, #-8]
    mov x0, x9
    ldr x9, [x29, #-144]
    mov x1, x9
    ldr x9, [x29, #-16]
    mov x2, x9
    bl swap
    str x0, [x29, #-152]
    ldr x9, [x29, #-24]
    mov x10, #1
    add x11, x9, x10
    str x11, [x29, #-160]
    ldr x0, [x29, #-160]
    b .Lpartition_exit
    mov x0, #0
    b .Lpartition_exit
.Lpartition_exit:
    add sp, sp, #160
    ldp x29, x30, [sp], #16
    ret
qsort:
    stp x29, x30, [sp, #-16]!
    mov x29, sp
    sub sp, sp, #80
    str x0, [x29, #-8]
    str x1, [x29, #-24]
    str x2, [x29, #-16]
    ldr x9, [x29, #-24]
    ldr x10, [x29, #-16]
    cmp x9, x10
    b.lt l8
    b l6
l8:
    ldr x9, [x29, #-8]
    mov x0, x9
    ldr x9, [x29, #-24]
    mov x1, x9
    ldr x9, [x29, #-16]
    mov x2, x9
    bl partition
    str x0, [x29, #-40]
    ldr x9, [x29, #-40]
    str x9, [x29, #-32]
    ldr x9, [x29, #-32]
    mov x10, #1
    sub x11, x9, x10
    str x11, [x29, #-48]
    ldr x9, [x29, #-8]
    mov x0, x9
    ldr x9, [x29, #-24]
    mov x1, x9
    ldr x9, [x29, #-48]
    mov x2, x9
    bl qsort
    str x0, [x29, #-56]
    ldr x9, [x29, #-32]
    mov x10, #1
    add x11, x9, x10
    str x11, [x29, #-64]
    ldr x9, [x29, #-8]
    mov x0, x9
    ldr x9, [x29, #-64]
    mov x1, x9
    ldr x9, [x29, #-16]
    mov x2, x9
    bl qsort
    str x0, [x29, #-72]
l6:
    mov x0, #0
    b .Lqsort_exit
.Lqsort_exit:
    add sp, sp, #80
    ldp x29, x30, [sp], #16
    ret
_start:
    adrp x9, a
    add x9, x9, :lo12:a
    mov x0, x9
    mov x9, #0
    mov x1, x9
    mov x9, #9
    mov x2, x9
    bl qsort
    str x0, [x29, #-8]
_exit:
    mov x0, #0
    mov x8, #93
    svc #0
