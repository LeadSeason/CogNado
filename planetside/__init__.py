from .planetside import Planetside


async def setup(bot):
    await bot.add_cog(Planetside(bot))
