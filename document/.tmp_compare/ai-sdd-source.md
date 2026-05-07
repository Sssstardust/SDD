# AI规范驱动(SDD)开发详解

## 前言

本文介绍AI驱动的规范驱动开发（SDD，Specification Drive Develop）。

它是一种基于AI进行业务开发的方法论，可以用多种工具链实现。目前使用较多的规范是spec-kit，BMAD。本文重点介绍spec-kit方法及工具。

SDD将软件开发中的规范(Specification)从一个静态的、开发前的文档，转变为一个贯穿整个开发生命周期的、动态的、可执行的核心组件。通过引入一个结构化的、分阶段的工作流程四，旨在弥合开发者意图与AI代码生成能力之间的鸿沟，从而在利
用AI提升效率的同时，确保软件产品的质量、可维护性和一致性。

## **规范驱动开发介绍**

spec-kit不仅仅是一套工具，它体现了一种独特的软件开发哲学。这种哲学建立在四大支柱之上，旨在为AI时代的软件工程提供一个更严谨、更可预测的范式。

### spec-kit的四大**支柱**

该项目的核心理念在其官方文档中有清晰的阐述，可归纳为以下四个基本原则:

- 意图驱动开发(Intent-Driven Development)

  这是spec-kit哲学的基石。它强调必须在定义“如何做”(技术实现)之前，先明确“做什么”(需求和目标)。这意味着开发过程始于对项目意图的深刻理解和清晰定义，而不是直接进入编码阶段。这一原则与某些敏捷方法论中通过实现来探索需求的做法形成了鲜明对比，它要求在启动开发前就形成一个稳定、明确的需求基线。

- 创建丰富的规范(Rich Specification Creation)

  该流程鼓励开发者创建详尽、全面的规范文档。这不仅仅是简单的功能列表，而是利用护栏和组织原则来引导AI。这些护栏可能包括性能指标、安全要求、代码风格标准等，它们共同构成了一个丰富的上下文环境，使Al能够生成更符合项目整体架构和质量标准的代码。

- 多步求精(Multi-Step Refinement)

  spec-kit明确拒绝了一键式代码生成的幻想。它推祟一个迭代求精的过程，开发被分解为多个阶段，每个阶段的产物(如规范、计划、任务)都会经过审查和完善，然后再进入下一阶段。这种渐进式的构建方式，确保了复杂性被有效管理，并且在每个步骤中都能及早发现和纠正偏差。

- 利用先进的Al能力(Leveraging Advanced AI Capabilities)

  整个工作流程都建立在现代大型语言模型能够理解复杂自然语言规范和技术计划的前提之上。它假定AI不仅能翻译指令，还能在一定程度上进行推理，从而将高层次的意图转化为具体的、可执行的代码。

### 支持的三种**开发**情境

spec-kit的设计旨在适应不同的软件开发场景，其文档中明确了三种主要的开发阶段或情境:

- 绿地开发(Greenfield，0-to-1)

  这是spec-kit最理想的应用场景。项目从零开始，开发者可以从高层次的需求出发，利用spec-kit的完整流程，逐步生成规范、计划、任务，并最终构建出生产就绪的应用程序。

- 创造性探索(Creative Exploration)

  在这个场景下，规范成为一个创新的基础。开发者可以利用同一份核心规范，指导AI生成多个并行的实现方案。例如，可以要求AI分别使用Rust和Go语言实现同一个组件以进行性能比较，或者通过修改规范中的用户界面描述来探索不同的UX模式，而无需手动重写大量代码。这极大地降低了技术选型和设计实验的成本。

- 棕地开发(Brownfield，迭代增强)

  这是最具挑战性的情境，即在现有系统中添加新功能或对遗留代码进行现代化改造。将spec-kit这种结构化的方法论追溯性地应用于已经存在的、复杂的项目中，会遇到相当大的阻力。外部评论者也指出，在棕地项目中评估这类工具的有效性本身就非常耗时和困难。

  深入分析spec-kit，可以发现它与主流的敏捷开发思想之间存在一种深刻的张力。敏捷宣言的核心在于拥抱变化、迭代开发和涌现式设计，而非遵循详尽的计划。然而，spec-kit的规范优先(spec-first)方法论重新引入了大规模的前期规划，其详尽的规范和技术计划阶段，在形式上类似于传统的瀑布模型或统一软件开发过程(RUP)中的重量级设计环节。

  采纳spec-kit绝非仅仅是引入一个新工具，而是一场深刻的文化和方法论变革。习惯于通过短周期迭代和持续重构来演进架构的团队，可能会发现spec-kit的流程过于僵化。该工具所强制执行的顺序性、计划驱动的流程，与现代DevOps和CI/CD文化所推崇的快速、小批量变更的理念可能存在冲突。因此，组织在考虑引入spec-kit时，必须评估其开发文化是否能够适应这种从响应变化到“遵循规范”的根本性转变。

## **工作流程**

spec-kit的核心价值体现在其结构化、可重复的工作流程中。这个流程旨在将高层次的业务意图，系统性地转化为经过验证的代码实现。

整个规范有一组MD（markdown）文件组成。每个md文件代表着软件开发过程中不同角色的输出。结合命令行工具，由AI完成软件生产的全流程。

### 项目初始化与章程(constitution)的建立

流程始于项目的初始化。开发者需要使用命令行进行安装，并运行specify
init命令来引导项目的基本结构。

此命令执行后，spec-kit会在项目中创建一个.specify目录，它作为项目的“记忆”中枢，存放着模板、脚本以及一个至关重要的文件，constitution.md(章程)

章程是整个项目的基石。开发者通过/speckit.constitution命令来创建或更新这个文件。其内容并非功能需求，而是项目的治理原则：

- 代码质量标准：如代码复杂度、命名规范、注释要求等。

- 测试标准：如单元测试覆盖率必须达到90%以上，必须包含集成测试等。

- 用户体验一致性：如所有界面元素必须遵循特定的设计系统。

- 性能要求：如API响应时间不得超过200毫秒。

章程确立后，AI代理在后续的所有阶段(从规范生成到代码实现)都必须严格遵守。它为AI的行为设定了不可逾越的边界，确保所有产出都符合项目的核心价值观和技术标准。

### **核心四阶段工作**

项目初始化并确立章程后，开发工作便进入了核心的四阶段循环。每个阶段都有明确的输入、输出，以及人类和AI各自扮演的角色。

<table>
<colgroup>
<col style="width: 19%" />
<col style="width: 15%" />
<col style="width: 22%" />
<col style="width: 29%" />
<col style="width: 13%" />
</colgroup>
<tbody>
<tr>
<td>阶段与命令</td>
<td>目的</td>
<td>开发者角色</td>
<td>AI行为</td>
<td>产出物</td>
</tr>
<tr>
<td><p>规范(Specify)</p>
<p>/speckit.specify</p></td>
<td>定义做什么和为什么</td>
<td>提供高层次、以用户为中心的需求描述，聚焦于业务目标、用户旅程和成功标准。</td>
<td>将高层次描述扩展为一份详尽的功能规范文档，包含用户故事、验收标准、工作流图等。</td>
<td>spec.md</td>
</tr>
<tr>
<td><p>计划(plan)</p>
<p>/speckit.plan</p></td>
<td>定义如何做</td>
<td>提供技术栈选型、架构模式、性能指标、安全合规等技术约束。</td>
<td>基于规范和技术约束，生成一份全面的技术实现计划，可能包括API设。计、数据库模式、组件分解、部署策略等。</td>
<td>plan.md</td>
</tr>
<tr>
<td><p>任务(tasks)</p>
<p>/speckit.tasks</p></td>
<td>分解工作</td>
<td>审查并批准规范和计划</td>
<td>将宏观的计划分解为一。系列具体的、小型的、可独立实现和测试的开发任务。</td>
<td>任务列表(通在tasks.md或项目管理工具中)</td>
</tr>
<tr>
<td><p>实现(Implement)</p>
<p>/speckit.implement</p></td>
<td>编写代码</td>
<td>审查AI生成的代码，验证其是否符合任务要求、规范和章程。角色转变为质量控制者和架构守护者。</td>
<td>逐一执行任务列表中的。任务，生成符合规范和计划的代码。</td>
<td>源代码、单元测试、相关配置文件等</td>
</tr>
</tbody>
</table>

#### **第一**阶段【规范(Specify)】

开发者首先使用/speckit.specify命令，用自然语言描述他们想要构建什么以及为什么。这里的重点是用户体验和业务价值，而非技术实现细节。AI代理会接收这些信息，并生成一份结构化的spec.md文件，其中可能包含详细的用户故事、验收标准和非功能性需求。

#### 第二阶段【计划(Plan)】

在功能规范获得批准后，开发者使用/speckit.plan命令，为项目注入技术层面的约束。这包括选择前端框架、后端语言、数据库类型，以及定义架构原则(如微服务vs.单体)、安全标准和性能目标。Al代理会综合spec.nd和这些技术约束，生成一份详细的plan.nd文件，作为后续编码工作的蓝图。

#### 第三**阶段【**任务(Tasks)】

规范和计划都确定下来后，/speckit.tasks命令的作用就是将这个宏伟的蓝图分解为可管理的、原子化的工作单元。AI会分析plan.md，生成一个详细的任务列表。每个任务都应该足够小，可以独立完成和验证，这类似于为AI代理创建了一个测试驱动开发(TDD)的流程。

#### 第四阶段【实现(Implement)】

开发者通过/speckit.inplenent命令(或类似机制)指示AI开始编码。AI会按照任务列表逐一实现功能。在这个阶段，开发者的角色从指令发出者转变为代码审查者和质量保证者。他们需要验证AI生成的代码是否准确地实现了任务目标，并且没有违反“章程”中定义的任何原则。

这个严谨的、环环相扣的流程，确保了从一个模糊的想法到一个具体的软件产品的转化过程是可追溯、可验证和高质量的。

## Spec-Kit技术**架构**

spec-kit的强大之处不仅在于其思想，还在于其灵活且可扩展的技术架构。该架构的设计目标是成为一个通用的、与具体AI技术解耦的流程编排擎。

### **工具链与技术**栈

spec-kit的一个核心架构决策是其技术中立性，即不与任何单一的AI模型或服务绑定。它被设计为一个通用的框架，可以与多种主流的AI编码代理协同工作。

大模型可以使用工具自带的，也可以指定使用。

推荐使用:

1.  qwen code

2.  Trae

3.  vscode

4.  Claude code(需要特别配置)

5.  Open code

- 核心语言

  工具包本身主要由Python编写，要求运行环境为Python3.11或更高版本。这表明
  其核心逻辑是基于脚本执行的，而非编译型语言。

- 依赖与工具

  项目推荐使用uv进行安装和包管理，这是一个现代的、高性能的Python包解析器
  和安装器。同时，Git是整个工作流程不可或缺的一部分，因为所有的规范、计划
  和代码产物都强调版本控制。

- 跨平台支持

  spec-kit通过提供两种类型的脚本来确保其在不同操作系统上的兼容性:为类Unix
  系统(Linux,
  macOS)提供shell脚本(sh)，为Windows系统提供PowerShell脚本(ps)。

### **仓库结构与关键组件**

对spec-kit的GitHub仓库进行分析，可以识别出几个关键的目录和组件，它们共同构成了工具包的功能核心:

- src/specify_cli

  这是工具包的心脏，包含了specify命令行接口(CLI)的核心逻辑。所有命令如init、check等的实现代码都位于此目录下。

- .specify/目录

  当用户在一个项目中运行specify
  init后，会自动生成这个目录。它扮演着项目的大脑或记忆的角色，存储着该项目特有的模板、脚本，以及最重要的constitution.nd文件。

- docs/目录

  包含项目的官方文档，是理解其设计哲学和使用方法的权威来源。

- 模板与提示(Templates and Prompts)

  spec-kit的真正威力并非来自其Python代码本身，而是来自其精心设计的、用于与AI交互的提示模板。这些模板被组织在不同的目录中，针对不同的AI代理和工作流程阶段进行了优化。本质上，spec-kit是一个复杂的提示工程框架，它将最佳实践固化为可复用的模板和脚本。

  不同工具的目录结构存在差异，以qwen code为例，templates目录如下：

  <img src="media/image1.png" style="width:4.18403in;height:3.04722in" />

## 工具链介绍

可以选择多种工具链实现spec-kit。

- Command line方式

1.  Qwen code

2.  Claude code

3.  Open code

- IDE方式

1.  Vscode

2.  Trae

### **基础环境**

- Node.js

  包括包管理工具，如pip，uv等

  **注意：不同的工具可能实际操作上会有区别，但是基本思路和过程是一致的，具体参
  考工具的使用方法。**

### **[Specify-CN](https://zhida.zhihu.com/search?content_id=266249862&content_type=Article&match_order=1&q=Specify-CN&zd_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJ6aGlkYV9zZXJ2ZXIiLCJleHAiOjE3NzAxNzQyODEsInEiOiJTcGVjaWZ5LUNOIiwiemhpZGFfc291cmNlIjoiZW50aXR5IiwiY29udGVudF9pZCI6MjY2MjQ5ODYyLCJjb250ZW50X3R5cGUiOiJBcnRpY2xlIiwibWF0Y2hfb3JkZXIiOjEsInpkX3Rva2VuIjpudWxsfQ.-bHoUMe6s6lBxahiUixLKwwKOlDfFVW2qp3jKvyzrqQ&zhida_source=entity)+Trae(或者VSCode)**

可视化ID不是必须的，所有的操作可以在命令行中完成。

**后续所有与git相关的操作都可以跳过。**

#### **[Specify-CN](https://zhida.zhihu.com/search?content_id=266249862&content_type=Article&match_order=1&q=Specify-CN&zd_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJ6aGlkYV9zZXJ2ZXIiLCJleHAiOjE3NzAxNzQyODEsInEiOiJTcGVjaWZ5LUNOIiwiemhpZGFfc291cmNlIjoiZW50aXR5IiwiY29udGVudF9pZCI6MjY2MjQ5ODYyLCJjb250ZW50X3R5cGUiOiJBcnRpY2xlIiwibWF0Y2hfb3JkZXIiOjEsInpkX3Rva2VuIjpudWxsfQ.-bHoUMe6s6lBxahiUixLKwwKOlDfFVW2qp3jKvyzrqQ&zhida_source=entity)安装**

- 安装speckit中文优化版

  pip install uv

> uv tool install specify-cn-cli --from
> git+https://gitcode.com/favornwpu/spec.kit.cn.git

- 输入以下命令检查是否安装成功

  specify-cn --help

> <img src="media/image2.png" style="width:5.75764in;height:2.16597in" />

- 获取最新版本

> uv tool install specify-cn-cli --force --from \\
>
> git+https://gitcode.com/favornwpu/spec.kit.cn.git
>
> 也可以使用https://github.com/figoliu/spec.xin作为安装源，输入以下命令安装：
>
> uv tool install specify-cn-cli --force --from
> git+https://github.com/figoliu/spec.xin.git
>
> 安装后重启PowerShell或者termianl重新连接。

#### **项目初始化**

> specify-cn init test2
>
> 选择ai助手，本项目选择claude。
>
> <img src="media/image3.png" style="width:5.75764in;height:2.08681in" />
>
> 选择脚本类型为ps，
>
> <img src="media/image4.png" style="width:5.76042in;height:0.79931in" />
>
> 执行如下：
>
> <img src="media/image5.png" style="width:5.76319in;height:2.95347in" />
>
> 以上执行过程可能需要通过翻墙工具完成（如获取最新版本需要访问github）。
>
> 命令执行完毕，后目录结构如下(选择的是claude风格的目录格式)，

<img src="media/image6.png" style="width:4.02361in;height:4.09375in" />

<img src="media/image7.png" style="width:4.02708in;height:2.41319in" />

#### Trae安装与导入SDD项目

> Trae正常下载安装后，需要完成注册才能进行AI对话。
>
> 通过菜单：文件-\>打开文件夹 导入speckit-cn初始化后生成的项目test2。
>
> 在Trae右侧的AI交互区域，使用下面下拉框中的命令，输入想要进行的SDD步骤，
> 即可进行SDD开发。
>
> <img src="media/image8.png" style="width:3.88333in;height:4.21042in" />

#### **项目开发详细介绍**

##### 生成项目章程

> Trae中与AI交互需要输入#号，不同的工具会不同，如claude code,qwen
> code使用 /作为命令输入工具。
>
> 输入#speckit.constitution，即可生成项目章程。

|  |
|----|
| \#speckit.constitution.md 创建专注于代码质量、测试标准、用户体验一致性和性能要求的原则. 包括这些原则应如何指导技术决策和实施选择的治理,要求文档为中文。 |

> 生成项目章程必须调用speckit.constitution.md文件，后面一部分是具体要求，比
> 如在章程里加入了文档为中文的要求。运行命令后，Trae会根据要求生成项目章程。
> 生成的章程放到.specify/memory/constitution.md文件中。
>
> 打开constitution.md，可以看到，文档按照要求的规范生成。
>
> <img src="media/image9.png" style="width:6.33403in;height:2.94653in" />
>
> **特别注意**：

- 章程不能放入太多内容，一般只放入3-5条核心原则

- 不能包含任何技术术语

- 加上中文强制要求，否则后续文档可能会使用英文

> 生成章程后，在AI的对话框输入更改需求。如果是团队项目，章程在团队开会讨
> 论后，可以更改需求；章程会自动递增版本，方面回溯管理。
> 最后确定章程后， 需要更新批准人和时间，确保所有成员都了解并同意章程。

##### 生成**项目**需求规格

> 这一步就是敏捷方法中的讲故事部分。
>
> 在Trae中的AI对话里输入以下命令生成项目需求规格：

|  |
|----|
| \#speckit.specify.md 开发一个登录系统，输入用户名，密码，传输过程为保障数据安全1，需要使用数字签名 |

> 生成项目需求规格必须调用#speckit.specify.md命令，后面一部分是具体要求。运行命令后，Trae会根据要求生成项目需求规格。生成的需求规格放到specs/spec.md文件中。
>
> **特别注意以下几点**：

- 需求不能包含任何技术术语，后续会专门生成技术相关内容

- 需求主要描述功能需求，非功能需求在后续文档中单独生成

- 可以详细描述用户故事，包括用户角色、触发条件、预期结果等

  生成项目需求规格如下所示：

  <img src="media/image10.png" style="width:5.76597in;height:3.84444in" />

  需求非常详细，主要包含需求的功能描述、非功能描述、用户故事等。

  需求需要人工仔细审核，确保符合项目章程的要求。修改方式可以通过AI对话修改或者手工修改。

  强烈建议对spec.md文件进行团队审议，确保符合要求。审议完毕后更新版本号和审议信息。

##### **澄清不明项**

项目需求规格中可能包含一些不明项，比如未定义的功能、未考虑的非功能需求等。需要与项目团队进行沟通，澄清这些不明项。

|  |
|----|
| \#speckit.clarify.md 澄清项目需求规格中的不明项，确保所有需求都被明确定义。 |

运行后，更新specs/test2/spec.md。

另外会在specs/test2/checklists/生成一个requirments.md文件，对需求的每一项检查并澄清，如果有需要，会自动更新需求文档。文档内容如下所示：

<img src="media/image11.png" style="width:4.67847in;height:4.06111in" />

##### **生成项目计划**

计划阶段是speckit最重要的一个阶段，也是最消耗时间的一个阶段。

在Trae中的AI对话里输入以下命令生成项目计划：

|  |
|----|
| \#speckit.plan.md 要求使用java springboot技术栈，处理用户请求，文档转换使用mkdocs工具。 |

生成项目计划调用speckit.plan.md文件，后面一部分是具体要求。运行命令后，speckit后连续做以下几个事情，

- 根据上下文生成一个研究计划，确定技术方面的实现方案。
  研究计划保存在specs/test2/research.md文件中。该计划包含所有技术方面的实现方案，比如使用哪些工具、哪些库、哪些框架等。需要认真审议该计划，并根据现实情况进行调整。

- 一个quickstart.md文件，包含项目的快速启动指南，比如如何安装依赖、如何运行项目等。

- 数据模型文档data-model.md，包含项目的数据模型，比如数据库表结构、数据字段等。

- 接口文档contact文件夹，包含项目的接口文档，比如RESTful API、GraphQL
  API等。

- 部署文档deployment.md，包含项目的部署指南，比如如何在不同环境部署项目等。

- 项目计划plan.md，包含项目的技术指标、文件目录结构等，注意这里的计划是技术指标，不是时间计划。

##### 

##### 

##### 生成**任务**

项目计划中包含了项目的技术指标，但是没有包含具体的任务列表。需要根据项目
计划，生成具体的任务列表。

|                    |
|--------------------|
| \#speckit.tasks.md |

行后项目会在specs/test2/生成一个tasks.md文件，包含所有需要完成的任务，以
及任务的负责人、时间估计等。文档内容如下所示：

生产内容如下：

<img src="media/image12.png" style="width:4.77917in;height:3.25in" />

speckit的任务模块非常强大，可以自动划分前置任务，确保任务按照正确的顺序
进行。任务还可以以传统团队的模型评估工作量以及优先级的排列等。

最新文档结构：

<img src="media/image13.png" style="width:4.04514in;height:5.03403in" />

<img src="media/image14.png" style="width:4.04028in;height:3.42778in" />

##### **一致性和覆盖率分析**

项目计划和任务列表生成后，需要进行一致性和覆盖率分析。确保所有任务都被覆
盖，并且没有重复或缺失的任务。

|                      |
|----------------------|
| \#speckit.analyze.md |

没有生成文件，但是有如下输出：

<img src="media/image15.png" style="width:5.13889in;height:2.58681in" />

分析报告中包含了所有任务的一致性和覆盖率分析结果。一致性分析确保所有任务
都被覆盖，没有重复或缺失的任务。

##### ** 项目实现**

项目实现阶段是根据项目计划和任务列表，开始实际编码和开发项目的阶段。需要
根据任务列表，分配给团队成员，开始独立开发。

|                        |
|------------------------|
| \#speckit.implement.md |

运行后项目会在specs/test2/生成一个implement-notes.md文件，包含所有 需
要完成的任务，以及任务的负责人、时间估计等。

**src目录为源代码目录，通过maven clean package
--Dmaven.test.skip=true编译成功。**

最终整个项目文件结构如下所示：

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td><p>C:.</p>
<p>│ mkdocs.yml</p>
<p>│ pom.xml</p>
<p>│</p>
<p>├─.claude</p>
<p>│ └─commands</p>
<p>│ speckit.analyze.md</p>
<p>│ speckit.checklist.md</p>
<p>│ speckit.clarify.md</p>
<p>│ speckit.constitution.md</p>
<p>│ speckit.fixbug.md</p>
<p>│ speckit.implement.md</p>
<p>│ speckit.plan.md</p>
<p>│ speckit.specify.md</p>
<p>│ speckit.tasks.md</p>
<p>│ speckit.taskstoissues.md</p>
<p>│</p>
<p>├─.specify</p>
<p>│ ├─memory</p>
<p>│ │ constitution.md</p>
<p>│ │</p>
<p>│ ├─scripts</p>
<p>│ │ └─powershell</p>
<p>│ │ check-prerequisites.ps1</p>
<p>│ │ common.ps1</p>
<p>│ │ create-new-feature.ps1</p>
<p>│ │ setup-plan.ps1</p>
<p>│ │ update-agent-context.ps1</p>
<p>│ │</p>
<p>│ └─templates</p>
<p>│ agent-file-template.md</p>
<p>│ checklist-template.md</p>
<p>│ plan-template.md</p>
<p>│ spec-template.md</p>
<p>│ tasks-template.md</p>
<p>│</p>
<p>├─docs</p>
<p>│ index.md</p>
<p>│</p>
<p>├─specs</p>
<p>│ └─001-user-login-digital-sign</p>
<p>│ │ analyze-report.md</p>
<p>│ │ data-model.md</p>
<p>│ │ plan.md</p>
<p>│ │ quickstart.md</p>
<p>│ │ research.md</p>
<p>│ │ spec.md</p>
<p>│ │ tasks.md</p>
<p>│ │</p>
<p>│ ├─checklists</p>
<p>│ │ requirements.md</p>
<p>│ │</p>
<p>│ └─contracts</p>
<p>│ api.yaml</p>
<p>│</p>
<p>└─src</p>
<p>├─main</p>
<p>│ ├─java</p>
<p>│ │ └─com</p>
<p>│ │ └─example</p>
<p>│ │ └─auth</p>
<p>│ │ │ AuthApplication.java</p>
<p>│ │ │</p>
<p>│ │ ├─config</p>
<p>│ │ │ SecurityConfig.java</p>
<p>│ │ │</p>
<p>│ │ ├─controller</p>
<p>│ │ │ AuthController.java</p>
<p>│ │ │ GlobalExceptionHandler.java</p>
<p>│ │ │</p>
<p>│ │ ├─model</p>
<p>│ │ │ LoginRequest.java</p>
<p>│ │ │ LoginResponse.java</p>
<p>│ │ │</p>
<p>│ │ ├─service</p>
<p>│ │ │ AuthService.java</p>
<p>│ │ │</p>
<p>│ │ └─util</p>
<p>│ │ SignatureUtil.java</p>
<p>│ │</p>
<p>│ └─resources</p>
<p>│ application.properties</p>
<p>│</p>
<p>└─test</p>
<p>└─java</p>
<p>└─com</p>
<p>└─example</p>
<p>└─auth</p>
<p>├─controller</p>
<p>│ AuthControllerTest.java</p>
<p>│</p>
<p>├─service</p>
<p>│ AuthServiceTest.java</p>
<p>│</p>
<p>└─util</p>
<p>SignatureUtilTest.java</p></td>
</tr>
</tbody>
</table>

### **Qwen Code+Qwen LLM**

### **Claud Code+DeepSeek**

### **OpenCode+Kimi**
