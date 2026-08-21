/**
 * 真实历史数据 — NIIMBOT Reddit 社区运营
 *
 * 数据来源：Reddit Dashboard 导出 2026-08-21
 * 数据性质：真实历史 Ground Truth（非模拟）
 *
 * 所有帖子均为已发布内容，包含实际 Views / Upvotes / Comments 数据。
 * 所有帖子均提及 NIIMBOT 标签机，属于品牌推广内容。
 *
 * 数据覆盖：
 *  - 20 个不同 Subreddit（niimbot_official, CraftFairs, resin, EtsySellers, EntrepreneurRideAlong, FemFragLab, assetmanagement, organizing, OutdoorsGear, peptideforums, Weddingsunder10k, fermentation, BambuLab, Printing, PeptidePathways, tirzepatidecompound, Retatrutide, homestead, propagation, succulents）
 *  - 29 条帖子，91 条评论
 *  - 使用场景：标签设计、产品标签、库存管理、资产标识、样本追踪、药品管理、组织规划
 *  - 部分评论提及竞品（Nelko / Phomemo / Orgbro / Brother / DYMO / Zebra / Munbyn）
 */

window.DEMO_DATA = {
  meta: {
    isMock: false,
    label: '真实历史数据',
    generatedAt: '2026-08-21',
    version: '20260821-real-v2',
    note: '基于 Reddit Dashboard 导出的真实历史数据。所有帖子、评论、浏览量均为实际数据。version 变更会触发自动重置本地缓存。'
  },

  posts: [
    // ---------- r/niimbot_official ----------
    {
      id: 'P-001',
      subreddit: 'niimbot_official',
      title: 'M2 guide: give crowded labels more room',
      body: 'When you build a label for the Niimbot M2, start with the information someone needs to spot first. Give that field the clearest position, then fit the secondary details around it. Using more of the available width is often easier to scan than squeezing every field into a small area.\n\nPrint one test label and put it on the actual object before making a full batch. Check it from the distance where you normally read it. If the layout still feels crowded, shorten the secondary text or move it to another line. The M2 has a maximum effective print width of 48 mm, so confirm that the label size and settings fit within that limit.',
      postedAt: '2026-08-20T20:00:45Z',
      url: 'https://www.reddit.com/r/niimbot_official/comments/1vtuax5/m2_guide_give_crowded_labels_more_room/',
      likes: 1,
      comments: 0,
      views: 4,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'official',
      brandRelation: 'official'
    },
    // ---------- r/CraftFairs ----------
    {
      id: 'P-002',
      subreddit: 'CraftFairs',
      title: 'Sixty candles and wax melts were ready, but the four label designs were not',
      body: 'I am getting ready for my first craft fair with four fragrance products. I made fifteen Cedar & Amber candles, fifteen Vanilla Oat candles, fifteen packs of Citrus wax melts, and fifteen packs of Lavender wax melts. That gave me sixty finished products to label and pack.\n\nFor this batch, each front product label stays on the retail package and goes home with the product. It carries the product name and price, while the candle safety labels and burning instructions remain separate. The four products use different package shapes, so each design still had to fit the actual jar, tin, box, clamshell, or bag used for that scent. That sounded simple until every wording or price change became another Canva page and I could no longer tell which four designs were final.\n\nI made one layout with a fixed place for the name and price, then wrote the final wording for all four products on paper. Before printing all sixty labels, I printed one test for each product and placed it on the actual retail package. Two names wrapped badly, so I shortened them and tested those two again.\n\nBecause these labels go home with the products, I was willing to spend more on the white PP thermal transfer stock than I would on temporary table price tags. Before printing the full batch, I put test labels from the same roll on each actual packaging surface. I exposed them to wax and oily residue, rubbed the packages as they would rub against one another in the bins, and then checked for edge lifting and loss of readability. Only after those samples stayed readable and attached did I use a Niimbot M2 to print four separate runs of fifteen.\n\nI counted fifteen labels against fifteen products in each bin and kept each finished stack with its matching scent. The version, material, and quantity checks are finished, and I no longer need to reopen Canva to work out which label is final.\n\nThe market has not happened yet, so I do not have a sales result. What I have is a finished packing box with four tested label designs, sixty labels, and four product bins that match. For my first event, getting that part settled feels like a good place to stop.',
      postedAt: '2026-08-20T16:49:37Z',
      url: 'https://www.reddit.com/r/CraftFairs/comments/1vtowlj/sixty_candles_and_wax_melts_were_ready_but_the/',
      likes: 1,
      comments: 1,
      views: 0,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'personal',
      brandRelation: 'promotional'
    },
    // ---------- r/resin ----------
    {
      id: 'P-003',
      subreddit: 'resin',
      title: 'I need a way to tell exactly which resin piece sold',
      body: 'I make one-off resin pieces for craft markets, and I reuse some of the same molds. Several finished pieces can therefore share a product name even though their colors and small details differ. After my last market, my handwritten tally told me which type of piece had sold. It could not tell me which individual piece had left the table, so I could not use the tally to confirm which photographed pieces were still in stock.\n\nI have started assigning a short number to each piece I am finishing for the next market. I print the small identifiers with a Niimbot M2 because only the number changes from one piece to the next. I record that number with the piece\'s photo now. If the piece sells at the market, I will copy the same number into the handwritten sales log instead of trying to identify it from a group photo later.\n\nThe numbering rule is ready, but the placement is not. A smooth underside will get a label only after a cured test sample passes an adhesion and removal check. If the base is textured, the number will stay on the removable bag. The full system has not been through a market yet, so I want that material decision settled before I print the complete set.\n\nIf you sell one-off resin pieces, have you had better luck putting the number underneath the piece or keeping it on removable packaging?',
      postedAt: '2026-08-20T16:40:34Z',
      url: 'https://www.reddit.com/r/resin/comments/1vtong6/i_need_a_way_to_tell_exactly_which_resin_piece/',
      likes: 2,
      comments: 2,
      views: 0,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'personal',
      brandRelation: 'promotional'
    },
    // ---------- r/EtsySellers ----------
    {
      id: 'P-004',
      subreddit: 'EtsySellers',
      title: 'The order tray reached packing, but its paper note stayed at the first bench',
      body: 'Our small handmade shop moves similar custom pieces through three areas. They start at the making bench, go to checking, and finish at packing.\n\nIn one batch, a tray completed that trip while its loose paper note stayed on the first bench. By the time we noticed, two similar pieces were sitting side by side in packing. We caught the mismatch before shipping. The order system had been correct all along, but the workshop had lost the link between the record and the physical piece.\n\nThe current pilot starts with the short codes from our order export. In a spreadsheet, each code appears four times, once for the fixed tray label and once beside each stage, MAKING, CHECK, and PACK. The fixed code stays on the tray for the whole trip. We replace only the stage tag at each handoff. Customer names, addresses, full order numbers, and design details remain in the order system.\n\nWe import the code-and-stage rows from Excel and use a Niimbot M2 to print the four labels for each order together. That keeps the code consistent without someone retyping it for every label. During the pilot, we are checking whether the fixed tray label rubs, lifts, or becomes hard to read as the tray moves between benches. At packing, we still open the original order and compare it with the finished piece. A tray code never counts as approval to ship.\n\nFor this first batch, three failures matter. We count damaged or missing fixed codes, stale stage tags, and trays that arrive in the wrong area. The labels can look tidy and still fail the handoff, so those three counts will decide whether the method stays.\n\nThe new failure we are watching most closely is a tray with the correct code and an old status. Examples from shops that have found a simple way to prevent that would be useful when we review the batch.',
      postedAt: '2026-08-20T08:53:06Z',
      url: 'https://www.reddit.com/r/EtsySellers/comments/1vtdz74/the_order_tray_reached_packing_but_its_paper_note/',
      likes: 0,
      comments: 4,
      views: 0,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'personal',
      brandRelation: 'promotional'
    },
    // ---------- r/EntrepreneurRideAlong ----------
    {
      id: 'P-005',
      subreddit: 'EntrepreneurRideAlong',
      title: 'Our skincare studio grew, and the sample fridge stopped making sense',
      body: 'I look after inventory and the less glamorous day-to-day jobs in a small skincare formulation studio. When everything fit in one room, sample locations lived mostly in our heads. That stopped working as we added storage and more people began using the same refrigerator.\n\nDuring a stock check, I went looking for a small reference sample of a peptide ingredient. It was still in the container supplied and labeled by the vendor. Our spreadsheet gave me a refrigerator, shelf, outer box, and position, but the map on the door still used a former team member\'s initials. The boxes had short project names on them. I knew the sample was still in stock and still had no idea which box to open.\n\nThe movement notes eventually led me to the person who had used it last, and together we found the right box. The supplier label was fine. Our own location notes were stale. After that, I dropped the initials and project nicknames from the map. Each spot now has a plain code made from the refrigerator, shelf, outer box, and position. The code is already in the spreadsheet and on the door map. I also prepared matching removable cards for the shelf and outer box, but those stay out of the refrigerator until the material test is complete.\n\nFor the cards, I used the Niimbot M2 that was already sitting on our packaging table for stock-bin labels. There were not many to print, and only the location code changed. I left the supplier containers alone. The map is attached to the outside of the refrigerator, where it stays at room temperature. Before any card goes inside, we test the material on the exact surface under the actual storage condition.\n\nThe outside map is already easier to follow because it uses the same printed code as the spreadsheet. Once the shelf and outer-box cards pass their material test, that code will continue all the way to the sample location. I used to know the whole refrigerator from memory. As the team grows, I cannot quietly remain the backup inventory system.',
      postedAt: '2026-08-20T08:51:02Z',
      url: 'https://www.reddit.com/r/EntrepreneurRideAlong/comments/1vtdxxe/our_skincare_studio_grew_and_the_sample_fridge/',
      likes: 1,
      comments: 0,
      views: 157,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'personal',
      brandRelation: 'promotional'
    },
    // ---------- r/FemFragLab ----------
    {
      id: 'P-006',
      subreddit: 'FemFragLab',
      title: 'My overnight blotters keep getting separated from their samples',
      body: 'I like returning to blotters the next morning. A blotter I dismissed at night can be the one I keep picking up at breakfast. This gets messy when I compare several samples from my collection in one sitting. The strips shift, the bottles go back in their tray, and a note such as \"the nice one\" becomes completely useless without a match.\n\nI am testing the idea on only a few samples before making a larger set. I used a Niimbot M2 to print each short number twice, once for the sample bottle and once for the dry end of its blotter. I only need the two numbers to match. The longer scent name and my actual notes stay in the notebook, so a strip that moves overnight can still lead me back to the right entry.\n\nThe bottle side of the small test was straightforward. The blotter is harder. I am comparing a flat tab with a folded flag, both kept at the dry end and away from the scented section. I am watching whether the flat tab lifts and whether the flag catches on anything or bends the strip.\n\nNumbering perfume samples sounded much too clinical when I first considered it. In the small test, I stopped noticing the number fairly quickly and went back to writing unhelpful but honest things like \"the nice one.\"\n\nThe matching-number idea is working in the small test, but I have not settled the attachment method, so I am holding off on a larger set. If you keep blotters overnight, do you label the dry end directly, fold a small flag around it, or keep the number off the blotter entirely?',
      postedAt: '2026-08-20T08:42:35Z',
      url: 'https://www.reddit.com/r/FemFragLab/comments/1vtdsxq/my_overnight_blotters_keep_getting_separated_from/',
      likes: 0,
      comments: 2,
      views: 0,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'personal',
      brandRelation: 'promotional'
    },
    // ---------- r/assetmanagement ----------
    {
      id: 'P-007',
      subreddit: 'assetmanagement',
      title: 'A routine service job exposed three names for the same machine',
      body: 'One of the two benchtop polishing machines in our small metalworking shop came up for routine service. I am the lead technician, so the work order landed with me. It used an asset number that appeared on neither machine. One housing carried an older sticker, and our maintenance binder called the same unit \"the polisher by the back wall.\"\n\nBefore touching either machine, I pulled the purchase record and the old service invoices. The serial number on one polisher matched the purchase record, and its service dates matched the binder. That gave us the current asset ID. I added the old sticker number to the history instead of peeling it off and pretending it had never existed.\n\nOur operations lead corrected the equipment register first. There were only two replacement tags, so I used the Niimbot M2 already on our bench for drawer and tool-cabinet labels. Each tag carries the confirmed asset ID and a QR code that opens the matching service record in read-only mode. The label stock had already passed our wiping and handling check on the same painted metal surface.\n\nWe also changed who is allowed to edit an asset ID. Technicians flag a mismatch and check the finished tag, while the operations lead verifies the records and makes the change. The routine service took less time than working out which polisher the order meant. We have retired \"the one by the back wall\" as an equipment name.',
      postedAt: '2026-08-20T08:35:16Z',
      url: 'https://www.reddit.com/r/assetmanagement/comments/1vtdoq0/a_routine_service_job_exposed_three_names_for_the/',
      likes: 1,
      comments: 0,
      views: 4,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'personal',
      brandRelation: 'promotional'
    },
    // ---------- r/organizing ----------
    {
      id: 'P-008',
      subreddit: 'organizing',
      title: 'I kept repeating the same fridge check every Sunday',
      body: 'Sunday evening already has a rhythm in my place. I choose a few outfits, look over the week ahead, and put Monday\'s things where I will see them in the morning.\n\nOne item on that list is a refrigerated prescription that I use on a fixed schedule set with my care team. The schedule stays exactly as prescribed. My organizing problem is that the weekly check has no visible ending. I compare the calendar with the pharmacy container, close the fridge, and sometimes repeat the whole thing later because I cannot remember whether I finished it or merely thought about it.\n\nOver the next two Sundays, I am trying a removable sleeve as the finish marker. I copy the weekday abbreviation and date from the existing plan onto it. One ribbon color marks the current week, while the other identifies the backup set so I do not mix them up. The vial stays in its pharmacy container, with the drug name, directions, pharmacy details, lot, and expiration date in view.\n\nI printed the sleeve markers with the Niimbot M2, so the weekday and date would match on the current and backup sets. Handwriting two tiny versions would have given me one more thing to compare. Along with condensation, lifted edges, rubbing, and fading, I am counting how often I reopen the calendar after the sleeve is marked. If I still repeat the check, the sleeves have added fridge clutter and they go. Any change to the prescribed plan still sends me back to the pharmacy label and the original instructions.\n\nTwo Sundays should be enough to tell me whether this deserves a place in the routine. I could use a second opinion from people who rely on visible done markers. Does the removable sleeve sound like enough of a finish line, or is there a simpler cue I am overlooking?',
      postedAt: '2026-08-20T08:29:04Z',
      url: 'https://www.reddit.com/r/organizing/comments/1vtdl3a/i_kept_repeating_the_same_fridge_check_every/',
      likes: 1,
      comments: 0,
      views: 88,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'personal',
      brandRelation: 'promotional'
    },
    // ---------- r/niimbot_official ----------
    {
      id: 'P-009',
      subreddit: 'niimbot_official',
      title: 'Label showcase event: share your setup by September 8',
      body: 'https://preview.redd.it/ummg1kmvr8kh1.jpg?width=1024&format=pjpg&auto=webp&s=79047a2a42e5ca735107c81d707bfe86da2e17c9\n\nHi everyone, the Niimbot mod team is running a Label Showcase Event in Discord. If you have a label setup you would like to share, post it in the #showcase channel. The event closes on September 8.\n\nOriginal label designs are welcome. You can also share a label adapted from an official Niimbot template, or a practical setup made with a Niimbot printer. Add a clear photo and a short note about what the label is used for so other members can follow the idea.\n\nJoin the Discord here:?[https://discord.gg/rKHpJThwCf](https://discord.gg/rKHpJThwCf)\n\nPost your entry in #showcase and use reactions to support the entries you like. When the event closes, the three posts with the most reactions will each receive one month of VIP membership.\n\nPlease share only work and photos you have permission to post. Remove names, addresses, order details, barcodes, and other private information before uploading. Your entry does not need to look like a finished design project. A useful label on a shelf, bin, package, or workspace belongs here too.',
      postedAt: '2026-08-18T16:38:09Z',
      url: 'https://www.reddit.com/r/niimbot_official/comments/1vrugk6/label_showcase_event_share_your_setup_by/',
      likes: 1,
      comments: 0,
      views: 0,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'official',
      brandRelation: 'official'
    },
    // ---------- r/niimbot_official ----------
    {
      id: 'P-010',
      subreddit: 'niimbot_official',
      title: 'Six checks for faint print or lifting labels',
      body: 'Faint text and lifting edges can come from different parts of the job. Change one thing at a time and print a single sample after each check. That makes it easier to see what fixed the problem.\n\n1. Match the canvas to the loaded label. Confirm that the size shown in the editor matches the label in the printer. Look for clipped text, codes touching the edge, or a layout that was copied from another size.\n2. Check the installed consumables. Use label stock and carbon ribbon supported by the exact model, then load them according to its guide. Niimbot M2 and M3 identify the installed material and adjust print density automatically. After changing stock, let recognition and paper positioning finish before printing a test label. There is no manual density control to set.\n3. Simplify the sample. Print a short line of plain text before testing a dense code or a crowded layout. If plain text is clear, inspect the design rather than changing several printer settings at once.\n4. Prepare the surface. Remove dust, oil, and cleaner residue, then let the spot dry before applying the label. Press across the whole label instead of testing adhesion by touching one corner.\n5. Check the curve. If an edge lifts from a bottle, cable, or small container, try a shorter layout or a supported material intended for that shape. Do not stretch the label around the object.\n6. Check the actual environment. Refrigeration, heat, sunlight, frequent handling, and oily contact are separate conditions. Confirm the material guidance for the real job instead of treating one successful sample as proof for every setting.\n\nIf the sample still fails, include the printer model, app version, label and ribbon codes, expected result, and a photo of the failed sample in a Help post. Remove order numbers, addresses, and other private information before uploading it.',
      postedAt: '2026-08-15T17:34:23Z',
      url: 'https://www.reddit.com/r/niimbot_official/comments/1vp8w1o/six_checks_for_faint_print_or_lifting_labels/',
      likes: 1,
      comments: 0,
      views: 281,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'official',
      brandRelation: 'official'
    },
    // ---------- r/OutdoorsGear ----------
    {
      id: 'P-011',
      subreddit: 'OutdoorsGear',
      title: 'How do you split up the small stuff on group camping trips?',
      body: 'The big gear is easy to sort out on group camping trips. A tent or sleeping bag usually has an obvious owner. It is the little stuff that ends up in whichever car or tote is closest. Headlamps, charging cables, lighters, spare stakes, and small tools all get mixed together.\n\nWe started making mugs and cutlery cases personal because people eat at different times. I put surnames on the hard cases with my Niimbot M2. Loose utensils, the stove, the wash basin, and the water container still stay in the shared kitchen bin.\n\nI do not want to make a checkout list for a weekend trip. I am leaning toward keeping anything you might need after dark personal, while setup gear stays in the shared tote. How does your group divide it?',
      postedAt: '2026-08-14T18:08:13Z',
      url: 'https://www.reddit.com/r/OutdoorsGear/comments/1voerhe/how_do_you_split_up_the_small_stuff_on_group/',
      likes: 1,
      comments: 4,
      views: 5300,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'personal',
      brandRelation: 'promotional'
    },
    // ---------- r/niimbot_official ----------
    {
      id: 'P-012',
      subreddit: 'niimbot_official',
      title: 'A quick reference for label size, reading distance, and material',
      body: 'Label size starts with the reading job, not with the amount of empty space on the object. Write down the first field, the usual viewing distance, and how often the information changes. Then choose a layout that gives the first field enough room.\n\n    Use case          Read first          Typical view       Material question\n    Small container  Short identifier    In hand            Does the supported label fit the curve?\n    Drawer            Item or category    At arm\'s length     Will the contents change often?\n    Shelf box         Location code       From a few steps    Is larger type more useful than another field?\n    Refrigerated item Identifier and date In hand            Is the material approved for that surface and environment?\n    \n\nMaterial comes after the layout because words such as refrigerated, oily, or outdoor do not identify a suitable label by themselves. Surface, handling, temperature, moisture, and replacement frequency all matter. A label used on a clean indoor drawer has a different job from one placed on a cold container or an outdoor planter.\n\nNiimbot models support different label ranges and consumables, so check the current guide for the exact printer before choosing stock. Do not carry a material claim from one model or surface to another. If the information changes every week, easy replacement may matter more than maximum service life. If the label is meant to stay, test one on the real surface before preparing the rest.',
      postedAt: '2026-08-14T15:32:53Z',
      url: 'https://www.reddit.com/r/niimbot_official/comments/1voaite/a_quick_reference_for_label_size_reading_distance/',
      likes: 1,
      comments: 0,
      views: 276,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'official',
      brandRelation: 'official'
    },
    // ---------- r/niimbot_official ----------
    {
      id: 'P-013',
      subreddit: 'niimbot_official',
      title: 'M2 small label guide: what earns a place on the label',
      body: 'Small labels usually become hard to read in the editor before they ever reach the object. One more date or note looks harmless on a large phone screen. On the printed label, it can force the name into smaller type and leave no clear first line.\n\nThe Niimbot M2 is a 300 dpi thermal transfer printer. That resolution is useful for small text, but it is better spent on clean letter shapes than on squeezing in a fifth line. Start with the field that lets someone identify the object without opening a separate record. Add another field only when it changes what the person does at that moment.\n\nOn a small bottle, that may be a name or reference code. A date belongs there only if someone checks it while holding the bottle. A spice jar needs the item name first, with an opened date or refill note below it when that information is actually used in the kitchen. Parts boxes often work with a part number and one useful locator. A plant tag can carry the variety and planting date while changing care notes stay in a notebook.\n\nFor repeated jobs, save a base layout as a reusable Niimbot template. Duplicate it for each group, then change the field names without rebuilding the margins and type hierarchy. Print one sample and read it where the object will be used. If two lines still compete, remove a field before reducing the type again.',
      postedAt: '2026-08-13T18:32:17Z',
      url: 'https://www.reddit.com/r/niimbot_official/comments/1vnj50y/m2_small_label_guide_what_earns_a_place_on_the/',
      likes: 1,
      comments: 1,
      views: 325,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'official',
      brandRelation: 'official'
    },
    // ---------- r/niimbot_official ----------
    {
      id: 'P-014',
      subreddit: 'niimbot_official',
      title: 'FAQ: thermal labels and thermal-transfer labels are different workflows',
      body: 'Thermal and thermal-transfer workflows use different consumables, so choose from the job rather than from the printer name.\n\nFor an indoor bin or a short project, ask how often the text will change and how quickly you can replace the label. For a refrigerated container, check the model��s approved material and the surface condition before printing. For oily handling, high heat, or direct sun, look for model-specific material guidance instead of assuming a general label rating covers it. A label that works on a clean desk may need a different plan on a greasy tool box or an outdoor crate.\n\nUse this order: identify the environment, check the supported width and consumables for the exact Niimbot model, print one sample, and record what happened in your own use. Community examples can point you to questions; the current manual remains the source for model-specific instructions.',
      postedAt: '2026-08-12T17:33:54Z',
      url: 'https://www.reddit.com/r/niimbot_official/comments/1vmkvl7/faq_thermal_labels_and_thermaltransfer_labels_are/',
      likes: 1,
      comments: 0,
      views: 206,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'official',
      brandRelation: 'official'
    },
    // ---------- r/peptideforums ----------
    {
      id: 'P-015',
      subreddit: 'peptideforums',
      title: 'I printed the label and forgot to save the layout',
      body: 'Most of my small labels followed the same general format, so I wanted one layout I could reopen instead of arranging the fields from scratch every time.\n\nOn my first label in Niimbot\'s VialCalc, the calculator had already worked out the dose. I still spent a while nudging the fields around because I wanted the label itself to look clean, then hit print. The label came out fine, so I closed the app and moved on.\n\nThe next time I needed a similar label, I went looking for that layout and realized I had never saved it. The annoying part was having the old print right next to me, looking exactly how I wanted, while I rebuilt the whole thing on my phone.\n\nNow I hit Save as soon as the layout looks right. Rebuilding it once was enough.',
      postedAt: '2026-08-12T17:31:23Z',
      url: 'https://www.reddit.com/r/peptideforums/comments/1vmkt3v/i_printed_the_label_and_forgot_to_save_the_layout/',
      likes: 1,
      comments: 1,
      views: 2800,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'personal',
      brandRelation: 'promotional'
    },
    // ---------- r/Weddingsunder10k ----------
    {
      id: 'P-016',
      subreddit: 'Weddingsunder10k',
      title: '($8-10K) What did you hand off on your wedding day that you were glad not to manage yourself?',
      body: 'I am trying to make our day-of plan less dependent on me answering texts. The big jobs have obvious owners, but the small handoffs are where I can see things falling apart. Someone needs to take the card box, someone needs to bring home the leftover food, and someone needs to make sure the decorations do not stay at the venue.\n\nI could make a detailed binder, but I doubt anyone wants to study a full schedule while carrying boxes through a parking lot. I would rather give each helper one job and enough information to finish it without calling us. I have started labeling the hard plastic totes by person and destination with my Niimbot, while the paper bags just get masking tape.\n\nWhat did you hand off successfully, and what did you wish you had kept under your own control?',
      postedAt: '2026-08-12T17:24:42Z',
      url: 'https://www.reddit.com/r/Weddingsunder10k/comments/1vmkmmq/810k_what_did_you_hand_off_on_your_wedding_day/',
      likes: 8,
      comments: 19,
      views: 33500,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'personal',
      brandRelation: 'promotional'
    },
    // ---------- r/fermentation ----------
    {
      id: 'P-017',
      subreddit: 'fermentation',
      title: 'How do you stop housemates from moving or tossing active ferments?',
      body: 'I share a kitchen, and the hardest part of keeping a ferment going is making sure everyone else knows the jar is still active. To someone who did not start it, a cloudy jar at the back of the counter can look abandoned. It can also get moved when somebody needs the space.\n\nClaiming one permanent shelf would be simple, but some jars are too tall and I do not think every shared surface should become off-limits. A group chat message also disappears quickly once other conversations start. For now, I use my Niimbot to put a small initials label on each reusable lid, while dates and batch notes stay on masking tape.\n\nWhat has worked in your kitchen? Do you use a dedicated area, mark who is responsible for each jar, or rely on everyone asking before they move anything?',
      postedAt: '2026-08-12T16:53:48Z',
      url: 'https://www.reddit.com/r/fermentation/comments/1vmjq37/how_do_you_stop_housemates_from_moving_or_tossing/',
      likes: 0,
      comments: 33,
      views: 20500,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'personal',
      brandRelation: 'promotional'
    },
    // ---------- r/BambuLab ----------
    {
      id: 'P-018',
      subreddit: 'BambuLab',
      title: 'Put the Bambu Studio preset name on the spool',
      body: 'I use filament from other brands with my Bambu Lab printer, and for some materials I keep more than one custom filament preset in Bambu Studio. I know which one I picked while the spool is loaded. After it goes back on the rack, the material and color still identify the filament, but they do not tell me which of those similar preset names belongs with it. The next time I load the spool, I have to open the list and work it out again.\n\nMy spool labels now have the material on the first line and the exact preset name on the second. I print them on my Niimbot when I open new spools. I leave temperature and cooling in Bambu Studio, where I already check them before printing. The physical label only needs to point me to the saved preset, so I am not maintaining the same settings in two places.',
      postedAt: '2026-08-12T16:50:16Z',
      url: 'https://www.reddit.com/r/BambuLab/comments/1vmjmgu/put_the_bambu_studio_preset_name_on_the_spool/',
      likes: 1,
      comments: 0,
      views: 2600,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'personal',
      brandRelation: 'promotional'
    },
    // ---------- r/EntrepreneurRideAlong ----------
    {
      id: 'P-019',
      subreddit: 'EntrepreneurRideAlong',
      title: 'I print my soap bands early and add the batch code last',
      body: 'I wrap each bar of soap with a paper band. The scent name and design stay the same when I make another batch of that soap, but the batch code changes. That code is how I match the finished bars to the notes in my batch notebook.\n\nBefore I started leaving the code area blank, I found a stack of bands left over from an older batch while packing for a market. They had the right scent name and design for the new bars, so at first they looked ready to use. Then I noticed the old batch code and put them aside.\n\nI still print the scent name and design before market week so that part is ready when I start packing, but I leave a blank spot for the batch code. After all the bars from one batch are wrapped, I check that batch\'s code in the notebook and print it on small adhesive labels with my Niimbot M2. I stick one label onto the blank spot on each paper band, then put those finished bars in the market box before I start wrapping the next batch.\n\nI usually have a few unused paper bands left when I finish. Since they do not have a batch code yet, I can set them aside without worrying that they have been mixed in with the finished bars.',
      postedAt: '2026-08-12T16:39:05Z',
      url: 'https://www.reddit.com/r/EntrepreneurRideAlong/comments/1vmjaz2/i_print_my_soap_bands_early_and_add_the_batch/',
      likes: 4,
      comments: 1,
      views: 6400,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'personal',
      brandRelation: 'promotional'
    },
    // ---------- r/Printing ----------
    {
      id: 'P-020',
      subreddit: 'Printing',
      title: 'Why my shipping labels and workspace labels use different printers',
      body: 'I used to think one label printer should handle everything. On my workbench, I ended up keeping two because shipping labels and workspace labels have very different jobs. My 4 x 6 direct thermal printer stays loaded with shipping stock, while I use a Niimbot M2 for thermal transfer labels that stay around the workspace. Size decides a few jobs, but where the label ends up matters more.\n\nAnything that leaves with an order goes through the direct thermal printer. It is already connected to my shipping setup and has the right stock loaded, so there is nothing to change in the middle of packing. For my bench, that is the convenient and less expensive choice for a shipping label that only needs to travel with one parcel.\n\nDrawer labels and reference tags are different. They stay in the workspace, get handled repeatedly, and may be there for a long time. I put those on the M2 because thermal transfer makes more sense to me for a label I expect to keep reading. Once the wording is settled, I would rather make one workspace label I plan to leave in place than treat it like another piece of temporary packing paperwork.\n\nI also wait until the information has stopped changing. A shelf position I am still testing gets a handwritten note for a while. If the drawer name or reference wording becomes part of my normal setup, I print the final version on the M2. I still choose the label stock and adhesive for the surface, but that is a separate decision from which printer handles the job.\n\nI still hesitate over project references that start as temporary and remain on the shelf months later. I leave the handwritten note alone while the project has an end date. If the reference quietly becomes part of the workspace, I replace the note with an M2 label. I still change my mind on those borderline jobs, but shipping and established workspace labels no longer compete for the same printer.',
      postedAt: '2026-08-12T16:34:14Z',
      url: 'https://www.reddit.com/r/Printing/comments/1vmj64r/why_my_shipping_labels_and_workspace_labels_use/',
      likes: 1,
      comments: 1,
      views: 1500,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'personal',
      brandRelation: 'promotional'
    },
    // ---------- r/niimbot_official ----------
    {
      id: 'P-021',
      subreddit: 'niimbot_official',
      title: 'Start here: show us the labeling problem you are solving',
      body: 'Welcome to the official Niimbot community. This is the place to get setup help, compare labeling workflows, share templates and print results, and leave product feedback.\n\nWhen you ask a question, tell us what you are labeling, the model you use, the label size or material, and the step that is failing. Say what you expected to happen. A quick sketch is often more useful than a photo. Please remove addresses, order numbers, serial numbers, and private records before posting.\n\nUse the Help flair for a problem, Workflow for a process question, Template for a layout, Print Result for an example, and Feedback for a request or suggestion. The sidebar and the pinned support post contain the current manual and official support entry points.',
      postedAt: '2026-08-11T17:14:58Z',
      url: 'https://www.reddit.com/r/niimbot_official/comments/1vlnn09/start_here_show_us_the_labeling_problem_you_are/',
      likes: 1,
      comments: 0,
      views: 163,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'official',
      brandRelation: 'official'
    },
    // ---------- r/niimbot_official ----------
    {
      id: 'P-022',
      subreddit: 'niimbot_official',
      title: 'Start here: rules, flair, and how to ask for help',
      body: 'Welcome to r/niimbot_official. Eight rules keep the feed useful: choose a relevant flair; give the model and label details when asking for help; describe one reproducible problem; remove personal or order information; do not post private support conversations; do not make medical or safety claims about a label; keep promotion and referral links out of support threads; and follow Reddit��s sitewide rules.\n\nThe seven flairs are Help, Setup, Workflow, Template, Print Result, Feature Request, and Feedback. If your post could fit two, choose the one that describes the action you want from readers.\n\nFor troubleshooting, include the model, tape or label size, connection method, app version, expected result, and the smallest reproducible symptom. Replies from accounts marked as official Niimbot moderators are the official response; other replies are community experience. Use the current support link in the sidebar for account, privacy, safety, or warranty questions.',
      postedAt: '2026-08-10T08:56:38Z',
      url: 'https://www.reddit.com/r/niimbot_official/comments/1vkfh7y/start_here_rules_flair_and_how_to_ask_for_help/',
      likes: 1,
      comments: 0,
      views: 161,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'official',
      brandRelation: 'official'
    },
    // ---------- r/PeptidePathways ----------
    {
      id: 'P-023',
      subreddit: 'PeptidePathways',
      title: 'Do you use a reusable vial label template with numeric fields?',
      body: 'I��m trying to stop rebuilding an entire small label when only the date, lot, or dose value changes. My current layout has a fixed header with the ID and reference code, plus variable slots for concentration, dose, date, and lot. I print with my Niimbot and want to change only the numbers in the template.\n\nIf you use automated label templates, how do you mark fixed and variable fields so a new person can edit the right values without changing the identifier? A screenshot of a blank or de-identified template would help.\n\nThis is about label layout and recordkeeping only.',
      postedAt: '2026-08-07T16:36:04Z',
      url: 'https://www.reddit.com/r/PeptidePathways/comments/1vi5lex/do_you_use_a_reusable_vial_label_template_with/',
      likes: 0,
      comments: 5,
      views: 6500,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'personal',
      brandRelation: 'promotional'
    },
    // ---------- r/tirzepatidecompound ----------
    {
      id: 'P-024',
      subreddit: 'tirzepatidecompound',
      title: 'What survives a cold-container handoff: ID, dose, or reference code?',
      body: 'After a container comes out of a cold box, I want the next person to identify it without opening the box or asking who packed it. I��m testing a Niimbot label order with ID first, then concentration and dose, date, and a reference code.\n\nThe open question is which field needs the strongest visual emphasis when the label is small and the surface is cold or damp. Do you keep dose and concentration together, or use a short ID on the container and leave the full record elsewhere?\n\nI��m asking about label layout and handoff checks only. I��m not making claims about materials, storage, dosing, or treatment.',
      postedAt: '2026-08-07T16:22:39Z',
      url: 'https://www.reddit.com/r/tirzepatidecompound/comments/1vi585b/what_survives_a_coldcontainer_handoff_id_dose_or/',
      likes: 0,
      comments: 4,
      views: 3000,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'personal',
      brandRelation: 'promotional'
    },
    // ---------- r/Retatrutide ----------
    {
      id: 'P-025',
      subreddit: 'Retatrutide',
      title: 'Can a five-field label stay readable on a small vial?',
      body: 'I��m doing a small-container label check with empty vials. The fields I need to fit are ID, concentration, dose, date, and lot/reference. The printer can place five lines; the real question is whether someone can read the dose and concentration without picking up the vial. I��m using a Niimbot printer to make the label samples for this layout test. Because some containers spend time in a cold box, I��m also comparing a thermal-transfer sample with a standard direct-thermal label after cold handling to see what stays legible.\n\nFor people who work with labeled peptide containers, what field order and type size have held up in practice? Do you keep both dose and concentration on the vial, or leave one in the linked record? I��m trying to separate what must be visible on the container from what can stay in the record.\n\nThis is a label-layout question only. The example uses no drug name, actual dose, or treatment instruction.',
      postedAt: '2026-08-07T16:11:26Z',
      url: 'https://www.reddit.com/r/Retatrutide/comments/1vi4x0g/can_a_fivefield_label_stay_readable_on_a_small/',
      likes: 0,
      comments: 6,
      views: 6300,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'personal',
      brandRelation: 'promotional'
    },
    // ---------- r/homestead ----------
    {
      id: 'P-026',
      subreddit: 'homestead',
      title: 'Keeping harvest crates identifiable after they leave the row',
      body: 'If you move produce from several rows or plots into one wash area, what do you write on the crate?\n\nI tried a few labels with my Niimbot and got stuck on the batch field. ��Tomatoes�� works until two similar varieties land in the same pile. Right now I��m testing:\n\nPLOT C / ROMA / 02\n\nI��m not sure what ��02�� should mean. Picking round? A date? A number in a notebook? If another person carries the crate to the wash area, they should not have to ask the picker what the code means.\n\nWhat do you use when several people share the sorting? I��m especially interested in a system that still makes sense after the crate has been handled and moved around.',
      postedAt: '2026-08-07T08:34:15Z',
      url: 'https://www.reddit.com/r/homestead/comments/1vhuwzt/keeping_harvest_crates_identifiable_after_they/',
      likes: 0,
      comments: 3,
      views: 3300,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'personal',
      brandRelation: 'promotional'
    },
    // ---------- r/homestead ----------
    {
      id: 'P-027',
      subreddit: 'homestead',
      title: 'Do you keep the seed source on the packet?',
      body: 'I\'m redoing a box of half-used seed packets. I started printing replacement labels with my Niimbot, and the source field is the one I can\'t decide on.\n\nVariety and year are staying. Those are the two things I can read without opening a notebook. Source feels useful when the same variety came from a seed swap and a catalog, but on most packets it just takes up room. I nearly added germination notes too, then realized I was turning each packet into a tiny record card.\n\nSeed savers: has the source ever helped you make a real decision later? Or do you write it down once and never look at it again?\n\nAt the moment I\'m leaning toward variety, year, and source only when it distinguishes two lots. Everything else can live in the notebook. I would rather leave one field blank than build a system I stop using next season.',
      postedAt: '2026-08-03T13:57:13Z',
      url: 'https://www.reddit.com/r/homestead/comments/1vee6ny/do_you_keep_the_seed_source_on_the_packet/',
      likes: 3,
      comments: 2,
      views: 5900,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'personal',
      brandRelation: 'promotional'
    },
    // ---------- r/propagation ----------
    {
      id: 'P-028',
      subreddit: 'propagation',
      title: 'Do you record the day roots first appear?',
      body: 'Do people really keep a \"first root\" date, and does it tell you anything useful later?\n\nThe date a cutting goes into water is straightforward. First root is fuzzier. One person might count the first little white bump; someone else might wait until there is an actual root to measure. That makes the date feel more precise than it really is.\n\nI\'m printing these jar labels with my Niimbot, and I\'m tempted to put only the start date and plant name on them. If something unusual happens, that can go in a note. Less satisfying, maybe, but much easier to keep up when there are several jars on the shelf.\n\nFor anyone who has been propagating for a while: which date do you still look at after the cutting has been potted, if any?',
      postedAt: '2026-08-03T13:51:49Z',
      url: 'https://www.reddit.com/r/propagation/comments/1vee1uk/do_you_record_the_day_roots_first_appear/',
      likes: 31,
      comments: 27,
      views: 33100,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'personal',
      brandRelation: 'promotional'
    },
    // ---------- r/succulents ----------
    {
      id: 'P-029',
      subreddit: 'succulents',
      title: 'Source or repot date: what gets the back of the plant tag?',
      body: 'The name belongs on the front of a succulent tag. I have no argument with that part. I print the small labels on my Niimbot and stick them to plain plastic tags. The back is where I run out of room.\n\nKeeping the nursery or seller seems worthwhile because that information disappears quickly after a repot. A repot date is less interesting, but probably more useful on an ordinary Tuesday when you\'re staring at a pot and trying to remember whether \"last year\" was ten months ago or closer to two years.\n\nI don\'t love codes for this. They\'re tidy until the notebook goes missing or the entry uses an older ID for the plant.\n\nIf you only keep one extra detail on the physical tag, which one has proved harder to reconstruct later: source or repot date? Also, does anyone actually use the back of the tag? That may be one of those ideas that works better on a desk than in a crowded pot.',
      postedAt: '2026-08-03T13:43:19Z',
      url: 'https://www.reddit.com/r/succulents/comments/1vedtx8/source_or_repot_date_what_gets_the_back_of_the/',
      likes: 1,
      comments: 2,
      views: 1500,
      hasImage: false,
      imageQuality: false,
      imageDescription: '',
      isPublished: true,
      authorType: 'personal',
      brandRelation: 'promotional'
    }
  ],

  comments: [
    // ---------- P-002 评论 ----------
    {
      id: 'C-001', postId: 'P-002',
      author: 'u/受众',
      text: 'Nice work. You did some good old fashioned problem solving with the least amount of waste.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-003 评论 ----------
    {
      id: 'C-002', postId: 'P-003',
      author: 'u/受众',
      text: 'Do you sign your pieces? I sign all of mine and could easily put a number next to or underneath my signature. Maybe you could do that?',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-003 评论 ----------
    {
      id: 'C-003', postId: 'P-003',
      author: 'u/受众',
      text: 'On the bottom will be just fine.. even if it doesnt come off completely, alcohol will get it off.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-004 评论 ----------
    {
      id: 'C-004', postId: 'P-004',
      author: 'u/受众',
      text: 'Tape. Just tape the note on at the first bench.\n\nTook me forever to figure out what you were going on about and what your actual question is, but.......tape.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-004 评论 ----------
    {
      id: 'C-005', postId: 'P-004',
      author: 'u/受众',
      text: 'this, or just have trays/boxes for each order with the catagories on a label, then tick off the label each time it moves, so no loose labels , one single labeland a single box per order.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-004 评论 ----------
    {
      id: 'C-006', postId: 'P-004',
      author: 'u/受众',
      text: 'This sounds more like a factory than a small handmade shop',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-006 评论 ----------
    {
      id: 'C-007', postId: 'P-006',
      author: 'u/受众',
      text: 'I just use the name or an abbreviation. I don\'t usually let them sit overnight either. Just a couple of hours will do. I\'ve got hundreds of samples, but I\'m usually testing as soon as I get them in small groups. It\'s not overwhelming that way.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-006 评论 ----------
    {
      id: 'C-008', postId: 'P-006',
      author: 'u/受众',
      text: 'I can��t believe you��re reading this much into something so simple.\n\nWrite the name of the perfume on one end of the blotter. Your sample bottles are labeled, right?',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-008 评论 ----------
    {
      id: 'C-009', postId: 'P-008',
      author: 'u/受众',
      text: 'I have an index card taped to my kitchen cabinet with a list of dated tasks. I check them off then they��re done with the pen that stays on the counter. There are also two other index cards with my kids�� chore charts and one for my vitamins. The last index card is where I write appointments and things for the week. This week is boring so it has four meetings with the date/time and an orthodontist appointment plus at the bottom is a reminder to buy protein powder.\n\nI have another index card on the bathroom wall with the dates of my period and a pen in my medicine cabinet.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-008 评论 ----------
    {
      id: 'C-010', postId: 'P-008',
      author: 'u/受众',
      text: 'Sometimes the hardest part of a routine isn��t doing the task, but remembering whether you actually did it. If the sleeve stops the repeated checking without adding too much clutter, I��d say it��s worth keeping.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-008 评论 ----------
    {
      id: 'C-011', postId: 'P-008',
      author: 'u/受众',
      text: 'I keep a tiny calendar magnet on the fridge. It was some sort of gift from a realtor but I tore the ad off it long ago. When my husband or myself give the dog her meds, we put a big check on the date. Easy peasy.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-008 评论 ----------
    {
      id: 'C-012', postId: 'P-008',
      author: 'u/受众',
      text: 'I use Medisafe App and mark off every med or routine once I take it or do it - otherwise I suffer from the same issue of did I take it or just think about it ?',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-011 评论 ----------
    {
      id: 'C-013', postId: 'P-011',
      author: 'u/受众',
      text: 'Were you previously sharing cutlery and headlamps?',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-011 评论 ----------
    {
      id: 'C-014', postId: 'P-011',
      author: 'u/受众',
      text: 'I get that the checklist can be annoying, but I really find it helpful. Even if it\'s more of a single list that goes in the tote so you know what\'s inside. This way you\'re not tracking every little thing throughout the weekend because dishes get shared, set somewhere new, etc. Now you\'re checking as things go back in so you know what\'s missing.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-011 评论 ----------
    {
      id: 'C-015', postId: 'P-011',
      author: 'u/受众',
      text: 'Everyone carries their own except things that weight dictates sharing - cook set, fuel, water filter, garmin����we divide this stuff up by weight as best we can.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-011 评论 ----------
    {
      id: 'C-016', postId: 'P-011',
      author: 'u/受众',
      text: 'This. Everyone is a self sufficient backpacker. Then decide on 2-3 things to share weight. Tent, stove, maybe large pot but likely not.\n\nAlternatively one person is the fully equipped backpacker. The other is the guest with just their personal gear and some shared weight.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-016 评论 ----------
    {
      id: 'C-017', postId: 'P-016',
      author: 'u/受众',
      text: 'I was very lucky and had a close friend who does event planning for her career, and she offered to be my day-of coordinator as my wedding gift. I cannot express what a difference this made for my day. If I had to go back and pay for one, I 100% would. Trust me, I know it��s hard to justify the cost when you��re planning ahead, but I know for certain that I would have had a very stressful and not-so-fun day had I not had her handling everything for me. The problem with assigning tasks ahead of time is that it does not account for all of the small things that absolutely will pop up day of. I would recommend looking into coordinators to see what you can manage, or, if you have a type-A, reliable, responsible friend who is willing to spend the day making sure yours runs smoothly, that could be an option as well. It is just a lot to ask of someone with no compensation.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-016 评论 ----------
    {
      id: 'C-018', postId: 'P-016',
      author: 'u/受众',
      text: 'SAMEEEE I had a friend who offered to plan the whole thing for me but I couldn\'t accept such a huge gift knowing how stressful that is. I DID accept her offer of day of coordinator and oh my god. I will never stop owing her for everything she did for me. I was able to enjoy my day and absolutely the same I would 100% pay for a coordinator if I didn\'t have her and if I knew what I know now. It is an extra cost that is worth every single penny. They are trained to know extra stuff to prevent things from going wrong before they happen, and are sooo useful for dealing with naughty bridal party and family members hahahahahaha. Our groomsmen were terrified of her and it made the day so much better!',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-016 评论 ----------
    {
      id: 'C-019', postId: 'P-016',
      author: 'u/受众',
      text: 'Yes! You don\'t need to hand off all the little jobs; you need to hand off the job of handing off all the little jobs. One of my aunts was my \"Clipboard Lady\". And I\'ve done it for friends, at a wedding in which my husband was a groomsman. Find someone organized and reliable who is in that sort of tier of friends and relations. It\'s actually a fun job for many people, especially if their relationship to someone in the wedding is such that they\'re gonna be there for everything anyway.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-016 评论 ----------
    {
      id: 'C-020', postId: 'P-016',
      author: 'u/受众',
      text: 'Your one-job-per-person instinct is right. Give each helper a tiny task card with the item, exact pickup time, destination, and one backup contact, like ��card box to Jamie��s locked car after speeches�� or ��rentals stacked by the loading door at 10:30.�� I��d keep cash, checks, and vendor payments with one trusted point person, then let everyone else own one physical handoff.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-017 评论 ----------
    {
      id: 'C-021', postId: 'P-017',
      author: 'u/受众',
      text: 'Labels with dates.\n\nPut what\'s in it, and what dated it was started.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-017 评论 ----------
    {
      id: 'C-022', postId: 'P-017',
      author: 'u/受众',
      text: 'Is \"if it\'s not yours, don\'t touch it\" just not being taught anymore? If fermenting is this big of an issue, probably keeping it in your room is going to be the only truly \"safe\" option.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-017 评论 ----------
    {
      id: 'C-023', postId: 'P-017',
      author: 'u/受众',
      text: 'If I were uneducated about fermentation, my best guess would be that the jars were rotten and needed to be trashed. (Of course this is not the real case, but OP\'s roommates might not know better.)\n\nI live with somebody who is extremely messy and lets their produce rot, so I know what living with messy people is like.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-017 评论 ----------
    {
      id: 'C-024', postId: 'P-017',
      author: 'u/受众',
      text: 'Giant label on the jar. Actually communicate?',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-017 评论 ----------
    {
      id: 'C-025', postId: 'P-017',
      author: 'u/受众',
      text: 'How about telling your housemates to leave your stuff alone, if that doesn\'t work, text them...',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-017 评论 ----------
    {
      id: 'C-026', postId: 'P-017',
      author: 'u/受众',
      text: 'I bought a pack of washable chalk markers, and I write on the jar. \n\nI write what it is, the date it was started, and the date I last checked it. I update that last one each time I burp or look at it.\n\nIt helps my husband see that the gross looking jar in the cupboard next to the plastic containers is alive and I am paying attention to it.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-017 评论 ----------
    {
      id: 'C-027', postId: 'P-017',
      author: 'u/受众',
      text: 'Oooh I like this! I\'ve been using kitchen tape and a marker, this is a way better idea. Thank you!',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-017 评论 ----------
    {
      id: 'C-028', postId: 'P-017',
      author: 'u/受众',
      text: 'I love them but one thing to note is that if I\'m doing anything really prone to leaking or messiness I just use a plain old sharpie - sharpie washes off glass jars with a bit of alcohol, but won\'t come off if, for example, your sauerkraut has a party and the bubbles push liquid over the top.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-017 评论 ----------
    {
      id: 'C-029', postId: 'P-017',
      author: 'u/受众',
      text: 'Solid tips, much appreciated! Do you ever use any fun colors of sharpie?',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-017 评论 ----------
    {
      id: 'C-030', postId: 'P-017',
      author: 'u/受众',
      text: 'Yes because I\'m a nerd with three sourdough starters - I color code them so I can keep track of which one I\'m feeding! ??',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-017 评论 ----------
    {
      id: 'C-031', postId: 'P-017',
      author: 'u/受众',
      text: 'Keep them in your room? I used to keep a 3 gallon carboy in my closet and as long as the door was mostly closed I couldn\'t smell it at all',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-017 评论 ----------
    {
      id: 'C-032', postId: 'P-017',
      author: 'u/受众',
      text: 'Label it: Jane\'s pickles [date] DON\'T THROW AWAY!',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-017 评论 ----------
    {
      id: 'C-033', postId: 'P-017',
      author: 'u/受众',
      text: 'Painter\'s Tape with names and dates is the standard in my kitchen. I like the bright green frog tape for extra visibility.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-017 评论 ----------
    {
      id: 'C-034', postId: 'P-017',
      author: 'u/受众',
      text: 'Label Do not throw away. That or store it in your bedroom.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-017 评论 ----------
    {
      id: 'C-035', postId: 'P-017',
      author: 'u/受众',
      text: 'Post-it Note: ��Touch this and die!�� And maybe a smiley face.??',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-017 评论 ----------
    {
      id: 'C-036', postId: 'P-017',
      author: 'u/受众',
      text: 'I created a fermentation station on a cafeteria tray, and no one was allowed ot touch anything on it without asking. You could also put a piece of masking tape on the jar and write DO NOT TOUCH with a Sharpie. It\'s really weird to me that your roommates would throw anything away if it wasn\'t theirs.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-017 评论 ----------
    {
      id: 'C-037', postId: 'P-017',
      author: 'u/受众',
      text: '\"Can you please stop throwing away my stuff? Atleast ask before you do so in the future\".',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-017 评论 ----------
    {
      id: 'C-038', postId: 'P-017',
      author: 'u/受众',
      text: 'Masking tape and a sharpie are your friends here. Write notes as needed.?',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-017 评论 ----------
    {
      id: 'C-039', postId: 'P-017',
      author: 'u/受众',
      text: 'What an obnoxious post.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-017 评论 ----------
    {
      id: 'C-040', postId: 'P-017',
      author: 'u/受众',
      text: 'Get a mini fridge for your bedroom.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-017 评论 ----------
    {
      id: 'C-041', postId: 'P-017',
      author: 'u/受众',
      text: 'You don\'t ferment in a fridge.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-017 评论 ----------
    {
      id: 'C-042', postId: 'P-017',
      author: 'u/受众',
      text: 'Don\'t you typically move a kraut to the fridge after it has sufficiently fermented?',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-017 评论 ----------
    {
      id: 'C-043', postId: 'P-017',
      author: 'u/受众',
      text: 'No, you store your ferments in a fridge when they��re done. If the smell bothers you get a second small fridge for your room and don��t plug it in. Bypass the kitchen.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-017 评论 ----------
    {
      id: 'C-044', postId: 'P-017',
      author: 'u/受众',
      text: 'Cover everything in cayenne. A light dusting should work. They��ll figure it out.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-019 评论 ----------
    {
      id: 'C-045', postId: 'P-019',
      author: 'u/受众',
      text: 'smart way to handle it. i do similar but with just a stamp, never thought to use the label printer for that part',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-023 评论 ----------
    {
      id: 'C-046', postId: 'P-023',
      author: 'u/受众',
      text: 'I use Nelko printer for my pens and vials, they are compact and yes, helps tracking dates, doses, update injection diary and so on. One good aspect of this printer - labels are moisture resistant; I tried other brands and types that are just paper, they often turn to crap with perspiration on the pens or vials when you take out of cold fridge. App has customizable templates library',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: true, competitorName: 'Nelko',
      userNeed: '', useCase: ''
    },
    // ---------- P-023 评论 ----------
    {
      id: 'C-047', postId: 'P-023',
      author: 'u/受众',
      text: 'I also use a Nelko and have to say, for the price it is actually a handy little printer. Less than $20 and so simple to use.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: true, competitorName: 'Nelko',
      userNeed: '', useCase: ''
    },
    // ---------- P-023 评论 ----------
    {
      id: 'C-048', postId: 'P-023',
      author: 'u/受众',
      text: 'That��s so much work:\n\nJust put 1 label on a pen that say. Concentration, dose protocol, what it is.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-023 评论 ----------
    {
      id: 'C-049', postId: 'P-023',
      author: 'u/受众',
      text: 'Pens labeled with peptide/user and the vials are labeled with concentration and reconstitution date.\n\nI also adjust BAC to hit 10 units per injection across everything except the spicy ones (KLOW and NAD+)',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-023 评论 ----------
    {
      id: 'C-050', postId: 'P-023',
      author: 'u/受众',
      text: 'I designed my labels for Niimbot using Claude and he created a html file where I could easily edit the batch or date an it would update the layout automatically and save a PNG file.\n\nIf you are ok to use AI ChatGPT or Claude can design something for you',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-024 评论 ----------
    {
      id: 'C-051', postId: 'P-024',
      author: 'u/受众',
      text: 'Who is labeling like this? Probably only OP.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-024 评论 ----------
    {
      id: 'C-052', postId: 'P-024',
      author: 'u/受众',
      text: 'May be better to ask a pharmacy sub.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-024 评论 ----------
    {
      id: 'C-053', postId: 'P-024',
      author: 'u/受众',
      text: 'Ask the person it��s intended for.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-025 评论 ----------
    {
      id: 'C-054', postId: 'P-025',
      author: 'u/受众',
      text: 'Just get a Niimbot and stop screwing around with this crap!',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-025 评论 ----------
    {
      id: 'C-055', postId: 'P-025',
      author: 'u/受众',
      text: 'I bought a great little printer that prints the perfect sized labels for 3ml vials. Orgbro X1 and it\'s ��12. The editing app is a bit fiddly but it does the job. You can add images and create QR codes within the app (handy for pointing to COAs)',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: true, competitorName: 'Orgbro',
      userNeed: '', useCase: ''
    },
    // ---------- P-025 评论 ----------
    {
      id: 'C-056', postId: 'P-025',
      author: 'u/受众',
      text: 'I have no experience with that type of label but I know that a 40*20mm label fits very well on a 3ml vial and i can comfortably fit several lines of readable text on those.\n\nFor what it\'s worth, I use a Niimbot M3 label maker and those hold up very well in a freezer.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-025 评论 ----------
    {
      id: 'C-057', postId: 'P-025',
      author: 'u/受众',
      text: 'May I tempt you with Phomemo PM344-WF? 300DPI, works with any no brand thermal rolls (niimbot rolls are chipped). Wi-Fi printer, borderless, prints 6x4 shipping labels too. Phomemo and niimbot has better SW than other yolo Chinese printer apps, but nothing beats design and print from your computer.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: true, competitorName: 'Phomemo',
      userNeed: '', useCase: ''
    },
    // ---------- P-025 评论 ----------
    {
      id: 'C-058', postId: 'P-025',
      author: 'u/受众',
      text: 'I created a label maker that will have what you need, you can change fields here',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-026 评论 ----------
    {
      id: 'C-059', postId: 'P-026',
      author: 'u/受众',
      text: '02 could be the second harvest from that plot, keeps it simple if you\'re doing multiple passes over the season. Adding a date works too but then you gotta remember when you planted them and when the first flush was\n\nplot c / roma / second pick reads clear enough for someone else to sort without asking',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-026 评论 ----------
    {
      id: 'C-060', postId: 'P-026',
      author: 'u/受众',
      text: 'Does it actually matter what row they came from? Are you tracking yields down to the row or anything?\n\nRealistically, only harvest date and variety matter. Print out a bunch of reusable tokens for varieties like Roma, sungold, beefsteak, etc. then place them in the crates during picking. Laser etched wood with a coat of clear acrylic works great. If you want, write the date on the back of the token with grease pencil.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-026 评论 ----------
    {
      id: 'C-061', postId: 'P-026',
      author: 'u/受众',
      text: 'I have only ever put the date harvested and the type of produce...\n\nIf you\'re sorting by row, you\'re going to need to name your rows and get smaller vessels to break them into more restricted batches. But I can\'t see any reason to do this, unless you\'re experimenting with fertilizers or something?',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-027 评论 ----------
    {
      id: 'C-062', postId: 'P-027',
      author: 'u/受众',
      text: 'I keep seed sources in the spreadsheet I have for tracking everything about my plants. Then just right numbers on the pots on case the tag gets lost and I easily know which plant that is.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-027 评论 ----------
    {
      id: 'C-063', postId: 'P-027',
      author: 'u/受众',
      text: 'Source is super important to me. I\'m always getting in seeds form new places, and if that place has consistently low germination %, then I\'m going to stop using them.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-028 评论 ----------
    {
      id: 'C-064', postId: 'P-028',
      author: 'u/受众',
      text: 'Lol never',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-028 评论 ----------
    {
      id: 'C-065', postId: 'P-028',
      author: 'u/受众',
      text: 'I have like 150 houseplants��',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-028 评论 ----------
    {
      id: 'C-066', postId: 'P-028',
      author: 'u/受众',
      text: 'I LOVE a good spreadsheet and used to keep detailed notes for all these things, now I just take pictures of all of the props and put them in ��props�� folder. It helps me way more to visually see the progress and dates',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-028 评论 ----------
    {
      id: 'C-067', postId: 'P-028',
      author: 'u/受众',
      text: 'I don��t know why this information would be necessary for me to know or remember',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-028 评论 ----------
    {
      id: 'C-068', postId: 'P-028',
      author: 'u/受众',
      text: 'Lol no. When I have a big plant maintenance day, I write all the stuff I do in a log but I don\'t label containers when roots appear or anything like that. That\'s way too much nonsense.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-028 评论 ----------
    {
      id: 'C-069', postId: 'P-028',
      author: 'u/受众',
      text: 'Yes, I keep a fairly detailed spreadsheet. But, I have a lot of plants and way too much time on my hands lol.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-028 评论 ----------
    {
      id: 'C-070', postId: 'P-028',
      author: 'u/受众',
      text: 'I\'ve never done this and really don\'t see much reason to unless you are running a nursery and planning when you want to have certain plants ready. It would get to be a lot with how many props I will have going and how many plants I have.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-028 评论 ----------
    {
      id: 'C-071', postId: 'P-028',
      author: 'u/受众',
      text: 'I put the date that it was potted, with the rooting method on the back when I make my little label stakes as I��m potting them up. That��s the part I need a frame of reference for when comparing how they��re establishing later as I have to chop them again (because polka dots need constant pruning to get bushy plants and not leggy ones; no matter how much light they get?? so high maintenance).',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-028 评论 ----------
    {
      id: 'C-072', postId: 'P-028',
      author: 'u/受众',
      text: 'No.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-028 评论 ----------
    {
      id: 'C-073', postId: 'P-028',
      author: 'u/受众',
      text: 'I prefer to label and date my plants to see the progress and also troubleshoot if it��s not doing as well as it should. I also experiment a lot so helps to see progress.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-028 评论 ----------
    {
      id: 'C-074', postId: 'P-028',
      author: 'u/受众',
      text: 'I mark on a little sign in each pot when I last repotted :) that��s all',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-028 评论 ----------
    {
      id: 'C-075', postId: 'P-028',
      author: 'u/受众',
      text: 'I do not.. but I have far too many�� but curious what you do for a living? Most people who do are spreadsheet people.\n\nEdit: missing word',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-028 评论 ----------
    {
      id: 'C-076', postId: 'P-028',
      author: 'u/受众',
      text: 'I don\'t have time for that. What\'s the purpose?',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-028 评论 ----------
    {
      id: 'C-077', postId: 'P-028',
      author: 'u/受众',
      text: 'I put the start date (tc��s, for acclimation), name of plant, record number (from my spreadsheet), and who I got/bought it from. Helps me know who has the most rugged tc��s. I haven��t started doing that with propping. Yet.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-028 评论 ----------
    {
      id: 'C-078', postId: 'P-028',
      author: 'u/受众',
      text: 'I used to in the beginning, then I owned too many plants to keep track. Now I only do when I\'m experimenting. My daughter and I wanted to figure out the quickest way roots grew. We did tap water that was refilled every 5 days, tap water that was filled only when it was empty enough for roots to start drying, one with purified water and one in soil.\n\nThe tap water that was left alone and only refilled when nearly empty grew the fastest, but the roots turned green after a month. Next quickest was the soil. Then the tap water that was refilled, the roots turned green after 2 months. Last was the purified water, which also had the most gnats in it, which surprised me.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-028 评论 ----------
    {
      id: 'C-079', postId: 'P-028',
      author: 'u/受众',
      text: 'I started a progression notebook about 1 1/2 month ago, but that��s mostly pictures of my plants with dates I took those pics (plus whatever else doodles I deem necessary). I��ve got zero idea how much more detailed of a tracker I��m going to do as my brain��s a bit too preoccupied trying to finagle the plant setup, but definitely not entirely excluding Imma gonna go down the rabbit hole and potentially do a whole spreadsheet and whatnot thing. Or just give zero shits and have fun with everything.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-028 评论 ----------
    {
      id: 'C-080', postId: 'P-028',
      author: 'u/受众',
      text: 'Is this for like giving your plants birthdays or something?',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-028 评论 ----------
    {
      id: 'C-081', postId: 'P-028',
      author: 'u/受众',
      text: 'I don\'t have the focus to record dates, fair play to you',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-028 评论 ----------
    {
      id: 'C-082', postId: 'P-028',
      author: 'u/受众',
      text: 'What day is it today? ????',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-028 评论 ----------
    {
      id: 'C-083', postId: 'P-028',
      author: 'u/受众',
      text: 'I just take pictures of my plants and put them in a seperate folder. I love looking at the olp pictures and see how much they grew ????',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-028 评论 ----------
    {
      id: 'C-084', postId: 'P-028',
      author: 'u/受众',
      text: 'I record an entry when I notice rooting sometimes. I��m much more likely to do it if it��s a very important prop or if it��s a small plant I got (rooted or unrooted) shipped to me and it��s struggling or taking forever to show any new growth. I don��t think it tells me anything later but I am v sentimental so I occasionally go back to the entry on the day I got the plant and scroll through to see all the progress and emotional milestones. I��ve gotten very lazy with it now that I have so many plants though ??',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-028 评论 ----------
    {
      id: 'C-085', postId: 'P-028',
      author: 'u/受众',
      text: 'For TCs, I put the deflask date, mostly because I can\'t remember.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-028 评论 ----------
    {
      id: 'C-086', postId: 'P-028',
      author: 'u/受众',
      text: 'I don\'t for my many water props, but I collected Mammilaria seeds and fern spores a few months ago, and I marked the start and germination dates. Also because I\'ve never germinated either of those before and I\'d like a record of the timeline because it really does take months. Both are in sealed containers and doing well!',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-028 评论 ----------
    {
      id: 'C-087', postId: 'P-028',
      author: 'u/受众',
      text: 'The date I placed in water or soil and the name. Enjoy!',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-028 评论 ----------
    {
      id: 'C-088', postId: 'P-028',
      author: 'u/受众',
      text: 'This is crazy',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-028 评论 ----------
    {
      id: 'C-089', postId: 'P-028',
      author: 'u/受众',
      text: 'Yup. Only when I\'m running tests I record the dates',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-029 评论 ----------
    {
      id: 'C-090', postId: 'P-029',
      author: 'u/受众',
      text: 'repot date is a lot more useful and way harder to remember ??',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    },
    // ---------- P-029 评论 ----------
    {
      id: 'C-091', postId: 'P-029',
      author: 'u/受众',
      text: 'Repot date for me.  But all the info is in a spreadsheet; plant name, extra ID if I have multiple, source, price, buy date, last repot date, died date, light meter reading and distance from lamp if not in a window.',
      score: 1, likes: 0, replyCount: 0, level: 0, parentCommentId: null,
      mentionsBrand: false, mentionsCompetitor: false, competitorName: '',
      userNeed: '', useCase: ''
    }
  ]
};
