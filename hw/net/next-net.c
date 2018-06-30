/*
 * QEMU NeXT Network (MB8795) emulation
 *
 * Copyright (c) 2011 Bryce Lanham
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
 * THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */
#include "qemu/osdep.h"
#include "exec/address-spaces.h"
#include "sysemu/sysemu.h"
#include "hw/hw.h"
#include "net/net.h"
#include "hw/m68k/next-cube.h"
#include "hw/sysbus.h"

/* debug NeXT ethernet */
// #define DEBUG_NET

#ifdef DEBUG_NET
#define DPRINTF(fmt, ...) \
    do { printf("NET: " fmt , ## __VA_ARGS__); } while (0)
#else
#define DPRINTF(fmt, ...) do { } while (0)
#endif

/* IRQs */
#define TX_I_DMA 0
#define RX_I_DMA 1
#define TX_I     2
#define RX_I     3

/* names could be better */
typedef struct NextDMA {
    uint32_t csr;
    uint32_t savedbase;
    uint32_t savedlimit;

    uint32_t baser;
    uint32_t base;
    uint32_t limit;
    uint32_t chainbase;
    uint32_t chainlimit;
    uint32_t basew;
} NextDMA;

typedef struct NextNetState {
    SysBusDevice parent_obj;

    uint8_t mac[6];
    qemu_irq *irq;

    NICState *nic;
    NICConf conf;

    NextDMA tx_dma;
    uint8_t tx_stat;
    uint8_t tx_mask;
    uint8_t tx_mode;

    NextDMA rx_dma;
    uint8_t rx_stat;
    uint8_t rx_mask;
    uint8_t rx_mode;

    uint8_t rst_mode;
} NextNetState;

#define TYPE_NEXT_NET "next-net"
#define NEXT_NET(obj) OBJECT_CHECK(NextNetState, (obj), TYPE_NEXT_NET)

static int nextnet_can_rx(NetClientState *nc);
static ssize_t nextnet_rx(NetClientState *nc, const uint8_t *buf, size_t size);

/* It's likely that all register reads are bytes, while all CSR r/w are longs */
static uint32_t net_readb(void *opaque, hwaddr addr)
{
    NextNetState *s = (NextNetState *)opaque;

    switch (addr) {
    case 0x6000: /* TXSTAT */
        DPRINTF("TXSTAT \tRead\n");
        return s->tx_stat;

    case 0x6001:
        DPRINTF("TXMASK \tRead\n");
        return s->tx_mask;

    case 0x6002:
        DPRINTF("RXSTAT \tRead %x\n", s->rx_stat);
        return s->rx_stat;

    case 0x6003:
        // DPRINTF("RXMASK \tRead\n");
        return s->rx_mask;

    case 0x6004:
        DPRINTF("TXMODE \tRead\n");
        return s->tx_mode;

    case 0x6005:
        // DPRINTF("RXMODE \tRead\n");
        return s->rx_mode;

    case 0x6006:
        DPRINTF("RSTMODE \tRead\n");
        return s->rst_mode;

    default:
        DPRINTF("NET Read B @ %x\n", (unsigned int)addr);
        return 0;
    }
}

static uint32_t net_readw(void *opaque, hwaddr addr)
{
    DPRINTF("S Read W @ %x\n", (unsigned int)addr);
    return 0;
}

static uint32_t net_readl(void *opaque, hwaddr addr)
{
    NextNetState *s = (NextNetState *)opaque;
    switch (addr) {
    case 0x110:
        // DPRINTF("TXCSR Read\n");
        return s->tx_dma.csr;
    case 0x4100:
        DPRINTF("SAVEDBASE Read\n");
        return s->tx_dma.savedbase;
    case 0x4104:
        DPRINTF("SAVELIMIT Read\n");
        return s->tx_dma.savedlimit;
    case 0x4114:
        DPRINTF("TXLIMIT Read\n");
        return s->tx_dma.limit;
    case 0x4310:
        DPRINTF("TXBASE Read\n");
        /* FUTURE :return nextdma_read(device, addr); */
        return s->tx_dma.basew;
    case 0x150:
        // DPRINTF("RXCSR Read %x\n", s->rx_dma.csr);
        return s->rx_dma.csr;
    case 0x4140:
        return s->rx_dma.savedbase;
    case 0x4144:
        // DPRINTF("SAVELIMIT %x @ %x\n",s->rx_dma.savedlimit, s->pc);
        return s->rx_dma.savedlimit;
    default:
        DPRINTF("NET Read l @ %x\n", (unsigned int)addr);
        return 0;
    }
}

#define NET_TXSTAT_CLEAR 0xFF
#define NET_RXSTAT_CLEAR 0xFF
static void net_writeb(void *opaque, hwaddr addr, uint32_t value)
{
    NextNetState *s = (NextNetState *)opaque;

    switch (addr) {
    case 0x6000:
        DPRINTF("TXSTAT \tWrite: %x\n", value);
        if (value == NET_TXSTAT_CLEAR) {
            s->tx_stat = 0x80;
        } else {
            s->tx_stat = value;
        }
        break;

    case 0x6001:
        DPRINTF("TXMASK \tWrite: %x\n", value);
        s->tx_mask = value;
        break;

    case 0x6002:
        // DPRINTF("RXSTAT \tWrite: %x\n", value);
        if (value == NET_RXSTAT_CLEAR) {
            s->rx_stat = 0x80;
        } else {
            s->rx_stat = value;
        }
        break;

    case 0x6003:
        // DPRINTF("RXMASK \tWrite: %x\n", value);
        s->rx_mask = value;
        break;

    case 0x6004:
        DPRINTF("TXMODE \tWrite: %x\n", value);
        s->tx_mode = value;
        break;

    case 0x6005:
        // DPRINTF("RXMODE \tWrite: %x\n", value);
        s->rx_mode = value;
        break;

    case 0x6006:
        DPRINTF("RSTMODE \tWrite: %x\n", value);
        s->rst_mode = value;
        break;

    case 0x600d:
        s->mac[(addr & 0xF) - 8] = value;
        DPRINTF("Set MAC ADDR %.2x:%.2x:%.2x:%.2x:%.2x:%.2x\n", s->mac[0],
                s->mac[1], s->mac[2], s->mac[3], s->mac[4], s->mac[5]);
        qemu_macaddr_default_if_unset((MACAddr *)&s->mac);
        break;

    case 0x6008:
    case 0x6009:
    case 0x600a:
    case 0x600b:
    case 0x600c:
        s->mac[(addr & 0xF) - 8] = value;
        break;

    case 0x6010:
    case 0x6011:
    case 0x6012:
    case 0x6013:
    case 0x6014:
        break;

    default:
        DPRINTF(" Write B @ %x with %x\n", (unsigned int)addr, value);
    }
}

static void net_writew(void *opaque, hwaddr addr, uint32_t value)
{
    DPRINTF("NET W w @ %x with %x\n", (unsigned int)addr, value);
}

static void net_writel(void *opaque, hwaddr addr, uint32_t value)
{
    static int tx_count;
    NextNetState *s = (NextNetState *)opaque;

    switch (addr) {
    case 0x110:
        if (value & DMA_SETENABLE) {
            size_t len = (0xFFFFFFF & s->tx_dma.limit) - s->tx_dma.base;
            uint8_t buf[1600]; /* needs to be in dma struct? */
            tx_count++;
            // if (tx_count % 4) return;
            DPRINTF("TXDMA ENABLE: %x len: %zu\n", s->tx_dma.base, len);
            DPRINTF("TX Enable\n");
            cpu_physical_memory_read(s->tx_dma.base, buf, len);

            qemu_send_packet(qemu_get_queue(s->nic), buf, len);
            s->tx_dma.csr |= DMA_COMPLETE | DMA_SUPDATE;
            s->tx_stat =  0x80;
            //  if (tx_count > 1510) vm_stop(VMSTOP_DEBUG);

            qemu_set_irq(s->irq[TX_I_DMA], 3);
        }
        if (value & DMA_SETSUPDATE) {
            s->tx_dma.csr |= DMA_SUPDATE;
        }
        if (value & DMA_CLRCOMPLETE) {
            s->tx_dma.csr &= ~DMA_COMPLETE;
        }
        if (value & DMA_RESET) {
            s->tx_dma.csr &= ~(DMA_COMPLETE | DMA_SUPDATE | DMA_ENABLE);
        }
        break;

    case 0x4100:
        DPRINTF("Write l @ %x with %x\n", (unsigned int)addr, value);
        s->tx_dma.savedbase = value;
        break;

    case 0x4104:
        DPRINTF("Write l @ %x with %x\n", (unsigned int)addr, value);
        s->tx_dma.savedlimit = value;
        break;
    case 0x4110:
        DPRINTF("Write l @ %x with %x\n", (unsigned int)addr, value);
        s->tx_dma.base = value;
        break;
    case 0x4114:
        DPRINTF("Write l @ %x with %x\n", (unsigned int)addr, value);
        s->tx_dma.limit = value;
        break;

    case 0x4310:
        DPRINTF("Write l @ %x with %x\n", (unsigned int)addr, value);
        s->tx_dma.base = value;
        /* FUTURE :nextdma_write(device, addr, value); */
        break;

    case 0x150:
        if (value & DMA_DEV2M) {
            DPRINTF("RX Dev to Memory\n");
        }

        if (value & DMA_SETENABLE) {
            s->rx_dma.csr |= DMA_ENABLE;
        }
        if (value & DMA_SETSUPDATE) {
            s->rx_dma.csr |= DMA_SUPDATE;
        }

        if (value & DMA_CLRCOMPLETE) {
            s->rx_dma.csr &= ~DMA_COMPLETE;
        }
        if (value & DMA_RESET) {
            s->rx_dma.csr &= ~(DMA_COMPLETE | DMA_SUPDATE | DMA_ENABLE);
        }

        DPRINTF("RXCSR \tWrite: %x\n", value);
        break;

    case 0x4150:
        // DPRINTF("Write l @ %x with %x\n",addr,value);
        s->rx_dma.base = value;
        // s->rx_dma.savedbase = value;
        break;

    case 0x4154:
        s->rx_dma.limit = value;
        // DPRINTF("Write l @ %x with %x\n",addr,value);
        break;

    case 0x4158:
        s->rx_dma.chainbase = value;
        // DPRINTF("Write l @ %x with %x\n",addr,value);
        break;

    case 0x415c:
        s->rx_dma.chainlimit = value;
        // DPRINTF("Write l @ %x with %x\n",addr,value);
        //DPRINTF("Pointer write %x w %x\n",addr,value);
        break;
    default:
        DPRINTF("Write l @ %x with %x\n", (unsigned int)addr, value);
    }

}

static uint64_t nextnet_mmio_readfn1(void *opaque, hwaddr addr, unsigned size)
{
    addr = (addr + 0x6000) & 0xffff;
    switch (size) {
    case 1:
        return net_readb(opaque, addr);
    case 2:
        return net_readw(opaque, addr);
    case 4:
        return net_readl(opaque, addr);
    default:
        g_assert_not_reached();
    }
}

static void nextnet_mmio_writefn1(void *opaque, hwaddr addr, uint64_t value,
                                  unsigned size)
{
    addr = (addr + 0x6000) & 0xffff;
    switch (size) {
    case 1:
        net_writeb(opaque, addr, value);
        break;
    case 2:
        net_writew(opaque, addr, value);
        break;
    case 4:
        net_writel(opaque, addr, value);
        break;
    default:
        g_assert_not_reached();
    }
}

static const MemoryRegionOps nextnet_mmio_ops1 = {
    .read = nextnet_mmio_readfn1,
    .write = nextnet_mmio_writefn1,
    .valid.min_access_size = 1,
    .valid.max_access_size = 4,
    .endianness = DEVICE_NATIVE_ENDIAN,
};

static uint64_t nextnet_mmio_readfn2(void *opaque, hwaddr addr, unsigned size)
{
    addr = (addr + 0x110) & 0xffff;
    switch (size) {
    case 1:
        return net_readb(opaque, addr);
    case 2:
        return net_readw(opaque, addr);
    case 4:
        return net_readl(opaque, addr);
    default:
        g_assert_not_reached();
    }
}

static void nextnet_mmio_writefn2(void *opaque, hwaddr addr, uint64_t value,
                                  unsigned size)
{
    addr = (addr + 0x110) & 0xffff;
    switch (size) {
    case 1:
        net_writeb(opaque, addr, value);
        break;
    case 2:
        net_writew(opaque, addr, value);
        break;
    case 4:
        net_writel(opaque, addr, value);
        break;
    default:
        g_assert_not_reached();
    }
}

static const MemoryRegionOps nextnet_mmio_ops2 = {
    .read = nextnet_mmio_readfn2,
    .write = nextnet_mmio_writefn2,
    .valid.min_access_size = 1,
    .valid.max_access_size = 4,
    .endianness = DEVICE_NATIVE_ENDIAN,
};

static int nextnet_can_rx(NetClientState *nc)
{
    NextNetState *s = qemu_get_nic_opaque(nc);

    return (s->rx_mode & 0x3) != 0;
}

static ssize_t nextnet_rx(NetClientState *nc, const uint8_t *buf, size_t size)
{
    NextNetState *s = qemu_get_nic_opaque(nc);

    DPRINTF("received packet %zu\n", size);

    /* Ethernet DMA is supposedly 32 byte aligned */
    if ((size % 32) != 0) {
        size -= size % 32;
        size += 32;
    }

    /* Write the packet into memory */
    cpu_physical_memory_write(s->rx_dma.base, buf, size);

    /*
     * Saved limit is checked to calculate packet size by both the rom
     * and netbsd
     */
    s->rx_dma.savedlimit = (s->rx_dma.base + size);
    s->rx_dma.savedbase = (s->rx_dma.base);

    /*
     * 32 bytes under savedbase seems to be some kind of register
     * of which the purpose is unknown as of yet
     */
    //stl_phys(s->rx_dma.base-32, 0xFFFFFFFF);

    if ((s->rx_dma.csr & DMA_SUPDATE)) {
        s->rx_dma.base = s->rx_dma.chainbase;
        s->rx_dma.limit = s->rx_dma.chainlimit;
    }
    /* we received a packet */
    s->rx_stat = 0x80;

    /* Set dma registers and raise an irq */
    s->rx_dma.csr |= DMA_COMPLETE; /* DON'T CHANGE THIS! */
    qemu_set_irq(s->irq[RX_I_DMA], 6);

    return size;
}

static void nextnet_irq(void *opaque, int n, int level)
{
    switch (n) {
    case TX_I:
        // next_irq(opaque, NEXT_ENTX_I);
        break;

    case RX_I:
        // next_irq(opaque, NEXT_ENRX_I);
        break;

    case TX_I_DMA:
        // next_irq(opaque, NEXT_ENTX_DMA_I);
        break;

    case RX_I_DMA:
        // next_irq(opaque, NEXT_ENRX_DMA_I);
        break;
    }
}

void nextnet_init(M68kCPU *cpu)
{
    DeviceState *dev;
    NextNetState *nns;
    NICInfo *ni = &nd_table[0];

    if (!ni->used) {
        return;
    }

    qemu_check_nic_model(ni, TYPE_NEXT_NET);
    dev = qdev_create(NULL, TYPE_NEXT_NET);
    qdev_set_nic_properties(dev, ni);
    qdev_init_nofail(dev);

    /* allocate TX/RX and DMA irqs */
    nns = NEXT_NET(dev);
    nns->irq = qemu_allocate_irqs(nextnet_irq, cpu, 4);
}

static NetClientInfo nextnet_info = {
    .type = NET_CLIENT_DRIVER_NIC,
    .size = sizeof(NICState),
    .receive = nextnet_rx,
    .can_receive = nextnet_can_rx,
    .receive = nextnet_rx,
};

static void nextnet_realize(DeviceState *dev, Error **errp)
{
    NextNetState *s = NEXT_NET(dev);
    MemoryRegion *regmem1 = g_new(MemoryRegion, 1);
    MemoryRegion *regmem2 = g_new(MemoryRegion, 1);
    MemoryRegion *sysmem = get_system_memory();
    uint8_t mac[6] = { 0x00, 0x00, 0x0f, 0x00, 0xf3, 0x02 };

    memcpy(&s->mac, mac, 6);  
    s->nic = qemu_new_nic(&nextnet_info, &s->conf, "NeXT MB8795", dev->id, s);
    qemu_format_nic_info_str(qemu_get_queue(s->nic), s->mac);

    /* register device register space */
    memory_region_init_io(regmem1, NULL, &nextnet_mmio_ops1, s, "next.net1",
                          0x1000);
    memory_region_add_subregion(sysmem, 0x2106000, regmem1);

    /*
     * and ethernet control/status registers...
     * ... including DMA for now, will seperate out later
     */
    memory_region_init_io(regmem2, NULL, &nextnet_mmio_ops2, s, "next.net2",
                          0x4400);
    memory_region_add_subregion(sysmem, 0x2000110, regmem2);
}

static Property nextnet_properties[] = {
    DEFINE_NIC_PROPERTIES(NextNetState, conf),
    DEFINE_PROP_END_OF_LIST(),
};

static void nextnet_class_init(ObjectClass *oc, void *data)
{
    DeviceClass *dc = DEVICE_CLASS(oc);

    set_bit(DEVICE_CATEGORY_NETWORK, dc->categories);
    dc->realize = nextnet_realize;
    dc->desc = "NeXT Ethernet Controller";
    dc->props = nextnet_properties;
}

static const TypeInfo nextnet_typeinfo = {
    .name          = TYPE_NEXT_NET,
    .parent        = TYPE_SYS_BUS_DEVICE,
    .instance_size = sizeof(NextNetState),
    .class_init    = nextnet_class_init,
};

static void nextnet_register_types(void)
{
    type_register_static(&nextnet_typeinfo);
}

type_init(nextnet_register_types)
