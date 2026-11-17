// Copyright (C) 2026 OpenDungeons Team
// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef ROOMMANAGERLISTITEM_H
#define ROOMMANAGERLISTITEM_H

#include <CEGUI/CEGUI.h>
#include <CEGUI/Font.h>
#include <CEGUI/ImageManager.h>
#include <CEGUI/widgets/ListboxTextItem.h>
#include <algorithm>
#include <cstdint>
#include <string>
#include <vector>
#include "traps/TrapType.h"

//! \brief An owner-data row with artwork, a short value and an optional health or production bar.
//! Rows are framed like the slots of the chosen room window mockups; a tile shows its number above its picture.
class RoomManagerListItem : public CEGUI::ListboxTextItem
{
public:
    //! \brief Keeps images owned by CEGUI and clamps progress to the visible bar.
    RoomManagerListItem(const std::string& text, uint32_t id,
        const std::vector<const CEGUI::Image*>& images, float progress = -1.0f, bool tile = false, uint32_t progressColour = 0xFF9BAA35) :
        CEGUI::ListboxTextItem(text, id), mImages(images), mProgress(progress), mTile(tile), mProgressColour(progressColour),
        mSuffixImage(nullptr)
    {
        setSelectionBrushImage("OpenDungeonsSkin/SelectionBrush");
        setTextParsingEnabled(false);
        setTextColours(CEGUI::Colour(0xFFF2C860));
    }
    //! \brief Adds a small picture and a short value at the right end of a row, as the hourglass and remaining time of a
    //! patient.
    void setSuffix(const CEGUI::Image* image, const std::string& text)
    {
        mSuffixImage = image;
        mSuffixText = text;
    }
    //! \brief Scales row and priority tile height with their owning page.
    CEGUI::Sizef getPixelSize() const override
    {
        const float width = getOwnerWindow() == nullptr ? 480.0f : getOwnerWindow()->getPixelSize().d_width;
        return CEGUI::Sizef(mTile ? width * 0.22f : width * 0.95f, width * (mTile ? 0.22f : 0.17f));
    }
    //! \brief Draws portraits and item pictures beside the values, with progress below; tiles draw their number above.
    void draw(CEGUI::GeometryBuffer& buffer, const CEGUI::Rectf& target, float alpha,
        const CEGUI::Rectf* clipper) const override
    {
        if(mTile)
        {
            drawTile(buffer, target, alpha, clipper);
            return;
        }
        const float height = getPixelSize().d_height;
        const float side = std::min(height * 0.72f, target.getWidth() * 0.16f);
        float x = target.left() + height * 0.08f;
        CEGUI::ColourRect colours(0xFFFFFFFF);
        colours.setAlpha(alpha);
        drawFrame(buffer, target, alpha, clipper);
        const float pictureTop = target.top() + (height - side) * 0.5f;
        for(const CEGUI::Image* picture : mImages)
        {
            if(picture != nullptr)
                picture->render(buffer, CEGUI::Rectf(x, pictureTop, x + side, pictureTop + side), clipper, colours);
            x += side + height * 0.04f;
        }
        CEGUI::Rectf textArea(target);
        textArea.d_min.d_x = x;
        textArea.d_min.d_y += height * 0.08f;
        CEGUI::ListboxTextItem::draw(buffer, textArea, alpha, clipper);
        float right = target.right() - height * 0.08f;
        const CEGUI::Font* font = getFont();
        if(font != nullptr && !mSuffixText.empty())
        {
            const CEGUI::String suffix(mSuffixText);
            const float width = font->getTextExtent(suffix);
            right -= width;
            font->drawText(buffer, suffix, CEGUI::Vector2f(right, target.top() + height * 0.08f), clipper,
                getModulateAlphaColourRect(getTextColours(), alpha));
            right -= height * 0.04f;
        }
        if(mSuffixImage != nullptr)
        {
            const float suffixSide = height * 0.30f;
            mSuffixImage->render(buffer, CEGUI::Rectf(right - suffixSide, target.top() + height * 0.06f, right,
                target.top() + height * 0.06f + suffixSide), clipper, colours);
            right -= suffixSide + height * 0.04f;
        }
        if(mProgress >= 0.0f)
        {
            const CEGUI::Image& brush = CEGUI::ImageManager::getSingleton().get("OpenDungeonsSkin/SelectionBrush");
            const float barRight = target.right() - height * 0.08f;
            const float top = target.top() + height * 0.62f;
            CEGUI::ColourRect background(0xFF302820);
            background.setAlpha(alpha);
            brush.render(buffer, CEGUI::Rectf(x, top, barRight, top + height * 0.12f), clipper, background);
            CEGUI::ColourRect fill(mProgressColour);
            fill.setAlpha(alpha);
            brush.render(buffer, CEGUI::Rectf(x, top, x + (barRight - x) * std::max(0.0f, std::min(1.0f, mProgress)),
                top + height * 0.12f), clipper, fill);
        }
    }
private:
    //! \brief Draws the thin gold slot frame of the mockups around one row.
    void drawFrame(CEGUI::GeometryBuffer& buffer, const CEGUI::Rectf& target, float alpha, const CEGUI::Rectf* clipper) const
    {
        const CEGUI::Image& brush = CEGUI::ImageManager::getSingleton().get("OpenDungeonsSkin/SelectionBrush");
        const float height = getPixelSize().d_height;
        const float edge = std::max(1.0f, height * 0.025f);
        const float inset = height * 0.03f;
        const CEGUI::Rectf box(target.left() + inset, target.top() + inset, target.right() - inset, target.top() + height - inset);
        CEGUI::ColourRect frame(0xFF8A6A34);
        frame.setAlpha(alpha);
        brush.render(buffer, CEGUI::Rectf(box.left(), box.top(), box.right(), box.top() + edge), clipper, frame);
        brush.render(buffer, CEGUI::Rectf(box.left(), box.bottom() - edge, box.right(), box.bottom()), clipper, frame);
        brush.render(buffer, CEGUI::Rectf(box.left(), box.top(), box.left() + edge, box.bottom()), clipper, frame);
        brush.render(buffer, CEGUI::Rectf(box.right() - edge, box.top(), box.right(), box.bottom()), clipper, frame);
    }
    //! \brief Draws a priority tile: the selection, the number centred above the picture and the picture in its frame.
    void drawTile(CEGUI::GeometryBuffer& buffer, const CEGUI::Rectf& target, float alpha, const CEGUI::Rectf* clipper) const
    {
        const float height = getPixelSize().d_height;
        const float numberHeight = height * 0.26f;
        const float side = std::min(height - numberHeight, target.getWidth() * 0.9f);
        const float left = target.left() + (target.getWidth() - side) * 0.5f;
        const float top = target.top() + numberHeight;
        if(isSelected() && getSelectionBrushImage() != nullptr)
            getSelectionBrushImage()->render(buffer, CEGUI::Rectf(left, top, left + side, top + side), clipper,
                getModulateAlphaColourRect(getSelectionColours(), alpha));
        CEGUI::ColourRect colours(0xFFFFFFFF);
        colours.setAlpha(alpha);
        if(!mImages.empty() && mImages.front() != nullptr)
            mImages.front()->render(buffer, CEGUI::Rectf(left + side * 0.08f, top + side * 0.08f, left + side * 0.92f,
                top + side * 0.92f), clipper, colours);
        drawFrame(buffer, CEGUI::Rectf(left, top, left + side, top + side), alpha, clipper);
        const CEGUI::Font* font = getFont();
        if(font == nullptr)
            return;
        const float width = font->getTextExtent(getText());
        font->drawText(buffer, getText(), CEGUI::Vector2f(target.left() + (target.getWidth() - width) * 0.5f,
            target.top() + std::max(0.0f, (numberHeight - font->getFontHeight()) * 0.5f)), clipper,
            getModulateAlphaColourRect(getTextColours(), alpha));
    }

    std::vector<const CEGUI::Image*> mImages;
    float mProgress;
    bool mTile;
    uint32_t mProgressColour;
    //! \brief Optional picture drawn before the suffix value at the right end of a row.
    const CEGUI::Image* mSuffixImage;
    //! \brief Optional short value drawn at the right end of a row.
    std::string mSuffixText;
};

//! \brief Returns an existing shared image without manufacturing a missing asset.
inline const CEGUI::Image* roomManagerImage(const std::string& name)
{
    CEGUI::ImageManager& images = CEGUI::ImageManager::getSingleton();
    return images.isDefined(name) ? &images.get(name) : nullptr;
}
//! \brief Uses the same existing trap icon as the build bar for every production order.
inline const CEGUI::Image* roomManagerTrapImage(TrapType type)
{
    static const char* const names[] = {"", "CannonButton", "SpikeTrapButton", "BoulderTrapButton",
        "WoodenDoorTrapButton", "IronboundDoorTrapButton", "SteelDoorTrapButton", "BarricadeTrapButton",
        "AlarmTrapButton", "FearTrapButton", "GasTrapButton", "LightningTrapButton", "FireburstTrapButton",
        "WatchBannerTrapButton", "SecretDoorTrapButton", "RunedDoorTrapButton", "TriggerTrapButton", "FreezeTrapButton"};
    const uint32_t index = static_cast<uint32_t>(type);
    return index > 0 && index < 18 ? roomManagerImage(std::string("OpenDungeonsIcons/") + names[index]) : nullptr;
}
//! \brief Marks the selected purse on a payer page as in the chosen mockups: the payer's medallion has the gold ring, the
//! coin and full colour, the other medallion a dark ring, no coin and dimmed colours. Both short labels stay visible.
inline void roomManagerPayer(CEGUI::Window* page, bool keeper)
{
    page->getChild("KeeperRing")->setProperty("ImageColours", keeper ? "FFFFFFFF" : "FF6A5E50");
    page->getChild("CreatureRing")->setProperty("ImageColours", keeper ? "FF6A5E50" : "FFFFFFFF");
    page->getChild("KeeperCoin")->setVisible(keeper);
    page->getChild("CreatureCoin")->setVisible(!keeper);
    page->getChild("Keeper")->setAlpha(keeper ? 1.0f : 0.55f);
    page->getChild("Creature")->setAlpha(keeper ? 0.55f : 1.0f);
    page->getChild("KeeperLabel")->setProperty("TextColours", keeper ? "FFF2C860" : "FF9A8C70");
    page->getChild("CreatureLabel")->setProperty("TextColours", keeper ? "FF9A8C70" : "FFF2C860");
}
#endif
